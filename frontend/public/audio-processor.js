/**
 * AudioWorkletProcessor — thay thế ScriptProcessorNode (deprecated).
 * Chuyển đổi float32 → int16 PCM và gửi qua port message.
 *
 * Ưu điểm so với ScriptProcessor:
 *   - Chạy trên audio thread riêng (không block main thread)
 *   - Latency thấp hơn (128 samples/frame thay vì 4096)
 *   - Không bị deprecation warning
 */
class PCMProcessor extends AudioWorkletProcessor {
  constructor() {
    super()
    this._buffer = new Float32Array(0)
    // Gom đủ 4096 samples mới gửi 1 lần (giống ScriptProcessor chunk size)
    // để không spam WebSocket quá nhiều messages
    this._chunkSize = 4096
  }

  process(inputs) {
    const input = inputs[0]
    if (!input || !input[0]) return true

    const float32 = input[0]

    // Append vào buffer
    const newBuf = new Float32Array(this._buffer.length + float32.length)
    newBuf.set(this._buffer, 0)
    newBuf.set(float32, this._buffer.length)
    this._buffer = newBuf

    // Gửi khi đủ chunk size
    while (this._buffer.length >= this._chunkSize) {
      const chunk = this._buffer.slice(0, this._chunkSize)
      this._buffer = this._buffer.slice(this._chunkSize)

      // Float32 → Int16
      const int16 = new Int16Array(chunk.length)
      for (let i = 0; i < chunk.length; i++) {
        const s = Math.max(-1, Math.min(1, chunk[i]))
        int16[i] = s < 0 ? s * 0x8000 : s * 0x7fff
      }

      this.port.postMessage(int16.buffer, [int16.buffer])
    }

    return true
  }
}

registerProcessor('pcm-processor', PCMProcessor)
