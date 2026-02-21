/**
 * AudioWorklet processor for buffering PCM audio from WebSocket.
 * Receives raw 16-bit stereo PCM at 48kHz via port messages.
 */
class PCMPlayerProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    // Ring buffer: 5 seconds at 48kHz stereo
    this.bufferSize = 48000 * 2 * 5;
    this.buffer = new Float32Array(this.bufferSize);
    this.writePos = 0;
    this.readPos = 0;
    this.samplesAvailable = 0;

    this.port.onmessage = (e) => {
      if (e.data instanceof ArrayBuffer) {
        this._writeFromPCM16(e.data);
      }
    };
  }

  _writeFromPCM16(arrayBuffer) {
    const view = new DataView(arrayBuffer);
    const numSamples = arrayBuffer.byteLength / 2; // 16-bit = 2 bytes per sample

    for (let i = 0; i < numSamples; i++) {
      const int16 = view.getInt16(i * 2, true); // little-endian
      const float32 = int16 / 32768.0;

      this.buffer[this.writePos] = float32;
      this.writePos = (this.writePos + 1) % this.bufferSize;
    }

    this.samplesAvailable = Math.min(
      this.samplesAvailable + numSamples,
      this.bufferSize
    );
  }

  process(inputs, outputs, parameters) {
    const output = outputs[0];
    if (!output || output.length < 2) return true;

    const left = output[0];
    const right = output[1];
    const frameCount = left.length; // typically 128

    for (let i = 0; i < frameCount; i++) {
      if (this.samplesAvailable >= 2) {
        // Interleaved stereo: L, R, L, R...
        left[i] = this.buffer[this.readPos];
        this.readPos = (this.readPos + 1) % this.bufferSize;
        right[i] = this.buffer[this.readPos];
        this.readPos = (this.readPos + 1) % this.bufferSize;
        this.samplesAvailable -= 2;
      } else {
        // Underrun: output silence
        left[i] = 0;
        right[i] = 0;
      }
    }

    return true;
  }
}

registerProcessor("pcm-player-processor", PCMPlayerProcessor);
