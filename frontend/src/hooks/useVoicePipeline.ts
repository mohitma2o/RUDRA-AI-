import { useEffect, useRef, useCallback } from 'react';
import { useVoiceStore } from '../store/voiceStore';

const WS_URL = 'ws://localhost:8000/ws/voice';
const SAMPLE_RATE = 16000;
const VAD_THRESHOLD = 0.025; // Energy threshold to trigger speech
const SILENCE_MS = 450;      // Silence trailing endpoint (ms)

export function useVoicePipeline() {
  const store = useVoiceStore();
  const wsRef = useRef<WebSocket | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const micStreamRef = useRef<MediaStream | null>(null);
  const audioQueueRef = useRef<{ source: AudioBufferSourceNode; onEnded: () => void } | null>(null);
  const isSpeakingRef = useRef<boolean>(false);
  const speechFramesRef = useRef<Float32Array[]>([]);
  const silenceTimerRef = useRef<number | null>(null);
  const lastStateRef = useRef<string>('idle');

  // Stop currently playing TTS audio (barge-in)
  const stopAudio = useCallback(() => {
    if (audioQueueRef.current) {
      try {
        audioQueueRef.current.source.stop();
      } catch {}
      audioQueueRef.current = null;
    }
  }, []);

  // Send an interrupt signal to the backend and kill current playback
  const interrupt = useCallback(() => {
    stopAudio();
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'interrupt' }));
    }
    store.setState('idle');
  }, [stopAudio, store]);

  // Play incoming audio buffer
  const playAudioChunk = useCallback(
    async (blobData: ArrayBuffer) => {
      stopAudio();
      try {
        if (!audioCtxRef.current) {
          audioCtxRef.current = new (window.AudioContext || (window as any).webkitAudioContext)();
        }
        const ctx = audioCtxRef.current;
        if (ctx.state === 'suspended') {
          await ctx.resume();
        }

        const audioBuf = await ctx.decodeAudioData(blobData.slice(0));
        const source = ctx.createBufferSource();
        source.buffer = audioBuf;
        source.connect(ctx.destination);

        store.setState('speaking');

        source.onended = () => {
          if (audioQueueRef.current?.source === source) {
            audioQueueRef.current = null;
            store.setState('idle');
          }
        };

        source.start(0);
        audioQueueRef.current = {
          source,
          onEnded: () => store.setState('idle'),
        };
      } catch (err) {
        console.error('Audio playback error:', err);
        store.setState('idle');
      }
    },
    [stopAudio, store]
  );

  // Send collected PCM frames as 16kHz 16-bit mono
  const flushUtterance = useCallback(() => {
    if (speechFramesRef.current.length === 0) return;

    // Concat Float32 frames
    const totalLength = speechFramesRef.current.reduce((acc, f) => acc + f.length, 0);
    const merged = new Float32Array(totalLength);
    let offset = 0;
    for (const frame of speechFramesRef.current) {
      merged.set(frame, offset);
      offset += frame.length;
    }
    speechFramesRef.current = [];

    // Convert Float32 [-1.0, 1.0] to Int16 PCM
    const pcm16 = new Int16Array(merged.length);
    for (let i = 0; i < merged.length; i++) {
      const s = Math.max(-1, Math.min(1, merged[i]));
      pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
    }

    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      // Send utterance metadata frame followed by binary PCM frame
      wsRef.current.send(JSON.stringify({ type: 'utterance', mode: store.mode }));
      wsRef.current.send(pcm16.buffer);
    }
  }, [store.mode]);

  // Connect WebSocket
  useEffect(() => {
    let reconnectTimeout: number;

    const connect = () => {
      const ws = new WebSocket(WS_URL);
      ws.binaryType = 'arraybuffer';
      wsRef.current = ws;

      let pendingAudioMeta: { turn: number; seq: number; lang: string } | null = null;

      ws.onopen = () => {
        store.setConnected(true);
        // Send initial settings
        ws.send(JSON.stringify({ type: 'config', ...store.settings }));
      };

      ws.onclose = () => {
        store.setConnected(false);
        reconnectTimeout = window.setTimeout(connect, 2000);
      };

      ws.onerror = (e) => {
        console.warn('WS error', e);
      };

      ws.onmessage = async (e) => {
        if (typeof e.data === 'string') {
          const msg = JSON.parse(e.data);
          switch (msg.type) {
            case 'state':
              lastStateRef.current = msg.state;
              store.setState(msg.state);
              break;
            case 'transcript':
              store.setTranscript(msg.text, msg.lang);
              break;
            case 'reply_delta':
              store.appendReply(msg.turn, msg.text);
              break;
            case 'turn_end':
              store.setTurnEnd(msg.turn);
              break;
            case 'timing':
              store.setTiming(msg);
              break;
            case 'audio':
              pendingAudioMeta = msg;
              break;
            case 'confirm':
              store.setConfirmPrompt({ tool: msg.tool, args: msg.args });
              break;
            default:
              break;
          }
        } else if (e.data instanceof ArrayBuffer && pendingAudioMeta) {
          await playAudioChunk(e.data);
          pendingAudioMeta = null;
        }
      };
    };

    connect();

    return () => {
      clearTimeout(reconnectTimeout);
      if (wsRef.current) wsRef.current.close();
    };
  }, [playAudioChunk, store]);

  // Microphone Setup with VAD
  useEffect(() => {
    let active = true;

    async function initMic() {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: {
            sampleRate: SAMPLE_RATE,
            channelCount: 1,
            echoCancellation: true,
            noiseSuppression: true,
            autoGainControl: true,
          },
        });

        if (!active) {
          stream.getTracks().forEach((t) => t.stop());
          return;
        }

        micStreamRef.current = stream;
        const ctx = new (window.AudioContext || (window as any).webkitAudioContext)({
          sampleRate: SAMPLE_RATE,
        });
        audioCtxRef.current = ctx;

        const source = ctx.createMediaStreamSource(stream);
        // Process in 2048 sample chunks
        const processor = ctx.createScriptProcessor(2048, 1, 1);

        processor.onaudioprocess = (e) => {
          const input = e.inputBuffer.getChannelData(0);

          // Calculate RMS energy
          let sumSquares = 0;
          for (let i = 0; i < input.length; i++) {
            sumSquares += input[i] * input[i];
          }
          const rms = Math.sqrt(sumSquares / input.length);
          const level = Math.min(100, Math.round(rms * 400));
          store.setAudioLevel(level);

          // Barge-in check: if assistant is speaking and user speaks loudly, interrupt!
          if (rms > VAD_THRESHOLD * 1.5 && lastStateRef.current === 'speaking') {
            interrupt();
          }

          if (rms > VAD_THRESHOLD) {
            // Speech detected
            if (!isSpeakingRef.current) {
              isSpeakingRef.current = true;
              if (store.state === 'idle') {
                store.setState('listening');
              }
            }
            if (silenceTimerRef.current) {
              clearTimeout(silenceTimerRef.current);
              silenceTimerRef.current = null;
            }
            speechFramesRef.current.push(new Float32Array(input));
          } else if (isSpeakingRef.current) {
            // Audio below threshold while currently in an utterance
            speechFramesRef.current.push(new Float32Array(input));
            if (!silenceTimerRef.current) {
              silenceTimerRef.current = window.setTimeout(() => {
                isSpeakingRef.current = false;
                silenceTimerRef.current = null;
                flushUtterance();
              }, SILENCE_MS);
            }
          }
        };

        source.connect(processor);
        processor.connect(ctx.destination);
      } catch (err) {
        console.error('Microphone init failed:', err);
      }
    }

    initMic();

    return () => {
      active = false;
      if (micStreamRef.current) {
        micStreamRef.current.getTracks().forEach((t) => t.stop());
      }
      if (audioCtxRef.current) {
        audioCtxRef.current.close();
      }
    };
  }, [flushUtterance, interrupt, store]);

  // Send typed query
  const sendTextQuery = useCallback((text: string) => {
    if (!text.trim()) return;
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'text', text }));
    }
  }, []);

  // Send confirm response
  const sendConfirmResponse = useCallback((approved: boolean) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'confirm', approved }));
    }
    store.setConfirmPrompt(null);
  }, [store]);

  return {
    interrupt,
    sendTextQuery,
    sendConfirmResponse,
  };
}
