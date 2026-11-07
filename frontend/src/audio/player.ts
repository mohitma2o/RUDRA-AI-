export class AudioPlayer {
  private context: AudioContext | null = null;
  private queue: ArrayBuffer[] = [];
  private currentSource: AudioBufferSourceNode | null = null;
  private generation = 0;
  private playing = false;

  constructor(
    private readonly onSpeakingChange: (speaking: boolean) => void,
    private readonly onError: (error: unknown) => void,
  ) {}

  get isSpeaking(): boolean {
    return this.playing;
  }

  enqueue(audioData: ArrayBuffer): void {
    this.queue.push(audioData);
    void this.playNext();
  }

  stop(): void {
    this.generation += 1;
    this.queue = [];
    const source = this.currentSource;
    this.currentSource = null;
    this.playing = false;
    if (source) {
      try {
        source.stop();
      } catch {}
    }
    this.onSpeakingChange(false);
  }

  async dispose(): Promise<void> {
    this.stop();
    const context = this.context;
    this.context = null;
    if (context && context.state !== 'closed') await context.close();
  }

  private async playNext(): Promise<void> {
    if (this.playing || this.queue.length === 0) return;
    this.playing = true;
    this.onSpeakingChange(true);
    const generation = this.generation;

    try {
      const context = this.getContext();
      if (context.state === 'suspended') await context.resume();

      while (this.queue.length > 0 && generation === this.generation) {
        const encoded = this.queue.shift();
        if (!encoded) continue;

        let audio: AudioBuffer;
        try {
          audio = await context.decodeAudioData(encoded.slice(0));
        } catch (error) {
          this.onError(error);
          continue;
        }
        if (generation !== this.generation) break;

        const source = context.createBufferSource();
        source.buffer = audio;
        source.connect(context.destination);
        this.currentSource = source;
        await new Promise<void>((resolve) => {
          source.onended = () => resolve();
          source.start();
        });
        if (generation === this.generation) this.currentSource = null;
      }
    } catch (error) {
      this.onError(error);
    } finally {
      if (generation === this.generation) {
        this.currentSource = null;
        this.playing = false;
        this.onSpeakingChange(false);
      }
    }
  }

  private getContext(): AudioContext {
    if (!this.context || this.context.state === 'closed') {
      this.context = new AudioContext();
    }
    return this.context;
  }
}
