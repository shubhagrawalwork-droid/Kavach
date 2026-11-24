// Runs on the audio thread. Converts the mic's native sample rate
// (usually 44.1 or 48 kHz) to 16 kHz, 16-bit PCM and sends ~250 ms chunks.
class MicProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.targetRate = 16000;
    this.ratio = sampleRate / this.targetRate; // `sampleRate` is a worklet global
    this.chunkSamples = this.targetRate / 4; // 250 ms
    this.out = new Int16Array(this.chunkSamples);
    this.outIndex = 0;
    this.pos = 0; // fractional read position in the incoming stream
    this.carry = new Float32Array(0);
  }

  process(inputs) {
    const channel = inputs[0] && inputs[0][0];
    if (!channel) return true;

    // join leftover samples from the last call with the new ones
    const data = new Float32Array(this.carry.length + channel.length);
    data.set(this.carry);
    data.set(channel, this.carry.length);

    while (this.pos + 1 < data.length) {
      const i = Math.floor(this.pos);
      const frac = this.pos - i;
      const sample = data[i] + (data[i + 1] - data[i]) * frac; // linear interpolation
      const clamped = Math.max(-1, Math.min(1, sample));
      this.out[this.outIndex++] = clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff;

      if (this.outIndex === this.chunkSamples) {
        this.port.postMessage(this.out.buffer.slice(0));
        this.outIndex = 0;
      }
      this.pos += this.ratio;
    }

    const consumed = Math.floor(this.pos);
    this.carry = data.slice(consumed);
    this.pos -= consumed;
    return true;
  }
}

registerProcessor("mic-processor", MicProcessor);
