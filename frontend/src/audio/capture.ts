const SAMPLE_RATE = 16000;

export class AudioCapture {
  private stream: MediaStream | null = null;
  private context: AudioContext | null = null;
  private node: AudioWorkletNode | null = null;
  private cancelled = false;
  private muted = false;

  async start(onFrame: (frame: Float32Array) => void): Promise<void> {
    this.cancelled = false;
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        sampleRate: SAMPLE_RATE,
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
    });
    if (this.cancelled) {
      stream.getTracks().forEach((track) => track.stop());
      return;
    }
    this.stream = stream;
    stream.getAudioTracks().forEach((track) => {
      track.enabled = !this.muted;
    });

    this.context = new AudioContext({ sampleRate: SAMPLE_RATE });
    if (this.context.sampleRate !== SAMPLE_RATE) {
      throw new Error(`The microphone audio context uses ${this.context.sampleRate} Hz; ${SAMPLE_RATE} Hz is required.`);
    }
    const workletUrl = new URL(`${import.meta.env.BASE_URL}capture-worklet.js`, window.location.href);
    await this.context.audioWorklet.addModule(workletUrl);
    if (this.cancelled) return;

    const source = this.context.createMediaStreamSource(this.stream);
    this.node = new AudioWorkletNode(this.context, 'rudra-capture', {
      numberOfInputs: 1,
      numberOfOutputs: 1,
      outputChannelCount: [1],
    });
    this.node.port.onmessage = (event: MessageEvent<Float32Array>) => {
      if (!this.muted) onFrame(event.data);
    };
    const mute = this.context.createGain();
    mute.gain.value = 0;
    source.connect(this.node);
    this.node.connect(mute);
    mute.connect(this.context.destination);
  }

  setMuted(muted: boolean): void {
    this.muted = muted;
    this.stream?.getAudioTracks().forEach((track) => {
      track.enabled = !muted;
    });
  }

  async stop(): Promise<void> {
    this.cancelled = true;
    this.node?.port.close();
    this.node?.disconnect();
    this.node = null;
    this.stream?.getTracks().forEach((track) => track.stop());
    this.stream = null;
    const context = this.context;
    this.context = null;
    if (context && context.state !== 'closed') await context.close();
  }
}
