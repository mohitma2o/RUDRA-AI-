class RudraCaptureProcessor extends AudioWorkletProcessor {
  process(inputs, outputs) {
    const channel = inputs[0]?.[0];
    if (channel) this.port.postMessage(channel.slice());
    for (const output of outputs) {
      for (const outputChannel of output) outputChannel.fill(0);
    }
    return true;
  }
}

registerProcessor('rudra-capture', RudraCaptureProcessor);
