class VADProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.isMuted = false;
    this.port.onmessage = (e) => {
      if (e.data.type === 'mute') this.isMuted = true;
      if (e.data.type === 'unmute') this.isMuted = false;
    };
  }

  process(inputs) {
    const input = inputs[0][0];  // mono channel
    if (!input || this.isMuted) return true;

    // Compute RMS energy
    let sum = 0;
    for (let i = 0; i < input.length; i++) sum += input[i] * input[i];
    const rms = Math.sqrt(sum / input.length);

    // Send raw PCM to main thread for WebSocket streaming
    // Send energy for UI waveform
    // Copy the input buffer to send it, because it might be overwritten by the browser.
    const pcmData = new Float32Array(input);
    
    this.port.postMessage({
      type: 'frame',
      pcm: pcmData.buffer,   // transferable
      energy: rms
    }, [pcmData.buffer]);

    return true;
  }
}
registerProcessor('vad-processor', VADProcessor);
