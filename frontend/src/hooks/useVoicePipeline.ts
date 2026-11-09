import { useCallback, useEffect, useRef } from 'react';
import { AudioCapture } from '../audio/capture';
import { AudioPlayer } from '../audio/player';
import { createVoiceSocket } from '../net/socket';
import { useVoiceStore } from '../store/voiceStore';

const SAMPLE_RATE = 16000;
const PRE_ROLL_SAMPLES = Math.round(SAMPLE_RATE * 0.3);
const MIN_SPEECH_SAMPLES = Math.round(SAMPLE_RATE * 0.25);
const MAX_SPEECH_SAMPLES = SAMPLE_RATE * 15;
const SILENCE_SAMPLES = Math.round(SAMPLE_RATE * 0.45);

export function useVoicePipeline() {
  const wsRef = useRef<WebSocket | null>(null);
  const captureRef = useRef<AudioCapture | null>(null);
  const playerRef = useRef<AudioPlayer | null>(null);
  const speechFramesRef = useRef<Float32Array[]>([]);
  const preRollFramesRef = useRef<Float32Array[]>([]);
  const preRollSamplesRef = useRef(0);
  const speechSamplesRef = useRef(0);
  const silenceSamplesRef = useRef(0);
  const noiseFloorRef = useRef(0.005);
  const isCollectingSpeechRef = useRef(false);

  if (!playerRef.current) {
    playerRef.current = new AudioPlayer(
      (speaking) => {
        const store = useVoiceStore.getState();
        if (speaking) store.setState('speaking');
        else if (store.state === 'speaking') store.setState('idle');
      },
      (error) => console.error('Audio playback error:', error),
    );
  }
  const player = playerRef.current;
  const retryRef = useRef<(() => Promise<void>) | null>(null);

  const clearUtterance = useCallback(() => {
    speechFramesRef.current = [];
    speechSamplesRef.current = 0;
    silenceSamplesRef.current = 0;
    isCollectingSpeechRef.current = false;
  }, []);

  const flushUtterance = useCallback(() => {
    const frames = speechFramesRef.current;
    const speechSamples = speechSamplesRef.current;
    clearUtterance();
    if (speechSamples < MIN_SPEECH_SAMPLES || frames.length === 0) {
      const store = useVoiceStore.getState();
      if (store.state === 'listening') store.setState('idle');
      return;
    }

    const totalLength = frames.reduce((total, frame) => total + frame.length, 0);
    const merged = new Float32Array(totalLength);
    let offset = 0;
    for (const frame of frames) {
      merged.set(frame, offset);
      offset += frame.length;
    }

    const pcm16 = new Int16Array(merged.length);
    for (let index = 0; index < merged.length; index += 1) {
      const sample = Math.max(-1, Math.min(1, merged[index]));
      pcm16[index] = sample < 0 ? sample * 0x8000 : sample * 0x7fff;
    }

    const socket = wsRef.current;
    if (socket?.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ type: 'utterance', mode: useVoiceStore.getState().mode }));
      socket.send(pcm16.buffer);
    }
  }, [clearUtterance]);

  const interrupt = useCallback(() => {
    player.stop();
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'interrupt' }));
    }
    useVoiceStore.getState().setState('idle');
  }, [player]);

  useEffect(() => {
    let active = true;
    let reconnectTimeout: number | undefined;
    let wsUrl = '';
    let token = '';
    let socket: WebSocket | null = null;

    const sendSettings = () => {
      if (socket?.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({ type: 'config', ...useVoiceStore.getState().settings }));
      }
    };

    const connect = () => {
      if (!active) return;
      socket = createVoiceSocket(wsUrl, token);
      wsRef.current = socket;
      let pendingAudioMeta: { turn: number; seq: number; lang: string } | null = null;

      socket.onopen = () => {
        const store = useVoiceStore.getState();
        store.setConnected(true);
        store.setConnectionDownSince(null);
        store.setBackendConfigError('');
        sendSettings();
      };
      socket.onclose = () => {
        const wasCurrentSocket = wsRef.current === socket;
        if (wasCurrentSocket) wsRef.current = null;
        const store = useVoiceStore.getState();
        store.setConnected(false);
        if (store.connectionDownSince === null) store.setConnectionDownSince(Date.now());
        if (active && wasCurrentSocket) reconnectTimeout = window.setTimeout(connect, 2000);
      };
      socket.onerror = (event) => console.warn('WebSocket error', event);
      socket.onmessage = (event) => {
        if (typeof event.data === 'string') {
          const message = JSON.parse(event.data);
          const store = useVoiceStore.getState();
          switch (message.type) {
            case 'state':
              if (!player.isSpeaking) store.setState(message.state);
              break;
            case 'transcript':
              store.setTranscript(message.text, message.lang);
              break;
            case 'reply_delta':
              store.appendReply(message.turn, message.text);
              break;
            case 'turn_end':
              store.setTurnEnd(message.turn);
              break;
            case 'timing':
              store.setTiming(message);
              break;
            case 'audio':
              pendingAudioMeta = message;
              break;
            case 'confirm':
              store.setConfirmPrompt({ tool: message.tool, args: message.args });
              break;
            case 'llm_status':
              store.setLLMStatus(message);
              break;
            case 'error':
              store.setErrorNotice({ code: message.code, message: message.message || 'The request failed.' });
              break;
            default:
              break;
          }
        } else if (event.data instanceof ArrayBuffer && pendingAudioMeta) {
          player.enqueue(event.data);
          pendingAudioMeta = null;
        }
      };
    };

    const unsubscribeSettings = useVoiceStore.subscribe((state, previousState) => {
      if (state.settings !== previousState.settings) sendSettings();
    });

    const configure = async (restart: boolean) => {
      try {
        if (!window.electronAPI) {
          throw new Error('Backend configuration is only available in the Rudra desktop app.');
        }
        if (restart) await window.electronAPI.restartBackend();
        const config = await window.electronAPI.getBackendConfig();
        if (!config?.wsUrl || !config.token) {
          throw new Error('Backend configuration unavailable.');
        }
        wsUrl = config.wsUrl;
        token = config.token;
        if (socket && socket.readyState !== WebSocket.CLOSED) socket.close();
        useVoiceStore.getState().setBackendConfigError('');
        connect();
      } catch (error) {
        if (!active) return;
        const message = error instanceof Error ? error.message : String(error);
        useVoiceStore.getState().setBackendConfigError(message || 'Backend configuration unavailable.');
      }
    };
    retryRef.current = () => configure(true);
    void configure(false);

    return () => {
      active = false;
      unsubscribeSettings();
      if (reconnectTimeout !== undefined) window.clearTimeout(reconnectTimeout);
      socket?.close();
      wsRef.current = null;
      useVoiceStore.getState().setConnected(false);
      retryRef.current = null;
    };
  }, [player]);

  useEffect(() => {
    const capture = new AudioCapture();
    captureRef.current = capture;

    const onFrame = (input: Float32Array) => {
      const frame = new Float32Array(input);
      let sumSquares = 0;
      for (const sample of frame) sumSquares += sample * sample;
      const rms = Math.sqrt(sumSquares / frame.length);
      const isCollecting = isCollectingSpeechRef.current;

      if (!isCollecting) {
        noiseFloorRef.current = Math.min(
          0.05,
          Math.max(0.002, noiseFloorRef.current * 0.95 + rms * 0.05),
        );
      }
      const threshold = Math.max(0.012, noiseFloorRef.current * 2.7);
      const store = useVoiceStore.getState();
      store.setAudioLevel(Math.min(100, Math.round(rms * 400)));

      if (player.isSpeaking && rms > Math.max(0.05, threshold * 1.5)) interrupt();

      if (isCollectingSpeechRef.current) {
        speechFramesRef.current.push(frame);
        if (rms > threshold) {
          speechSamplesRef.current += frame.length;
          silenceSamplesRef.current = 0;
        } else {
          silenceSamplesRef.current += frame.length;
        }
        if (
          silenceSamplesRef.current >= SILENCE_SAMPLES ||
          speechSamplesRef.current >= MAX_SPEECH_SAMPLES
        ) {
          flushUtterance();
        }
      } else if (rms > threshold) {
        isCollectingSpeechRef.current = true;
        speechFramesRef.current = [...preRollFramesRef.current, frame];
        speechSamplesRef.current = frame.length;
        silenceSamplesRef.current = 0;
        preRollFramesRef.current = [];
        preRollSamplesRef.current = 0;
        store.setState('listening');
      } else {
        preRollFramesRef.current.push(frame);
        preRollSamplesRef.current += frame.length;
        while (preRollSamplesRef.current > PRE_ROLL_SAMPLES) {
          const removed = preRollFramesRef.current.shift();
          if (!removed) break;
          preRollSamplesRef.current -= removed.length;
        }
      }
    };

    void capture.start(onFrame).catch(async (error: unknown) => {
      await capture.stop();
      console.error('Microphone initialization failed:', error);
      useVoiceStore.getState().setState('idle');
    });

    return () => {
      captureRef.current = null;
      clearUtterance();
      preRollFramesRef.current = [];
      preRollSamplesRef.current = 0;
      void capture.stop();
      void player.dispose();
    };
  }, [clearUtterance, flushUtterance, interrupt, player]);

  const sendTextQuery = useCallback((text: string) => {
    if (!text.trim()) return;
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'text', text }));
    }
  }, []);

  const sendConfirmResponse = useCallback((approved: boolean) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'confirm', approved }));
    }
    useVoiceStore.getState().setConfirmPrompt(null);
  }, []);

  const retryConnection = useCallback(async () => {
    await retryRef.current?.();
  }, []);

  return {
    interrupt,
    sendTextQuery,
    sendConfirmResponse,
    retryConnection,
  };
}
