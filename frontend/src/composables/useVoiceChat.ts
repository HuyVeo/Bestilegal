import { ref, onUnmounted } from 'vue'
import { useChatStore } from '@/stores/chat'

export type VoiceState =
  | 'idle'           // Chưa kết nối
  | 'connecting'     // Đang kết nối WebSocket
  | 'listening'      // VAD đang lắng nghe
  | 'recording'      // User đang nói (VAD phát hiện speech)
  | 'processing'     // STT / RAG / LLM đang xử lý
  | 'speaking'       // AI đang phát âm thanh
  | 'error'

export function useVoiceChat() {
  const chatStore = useChatStore()

  const voiceState = ref<VoiceState>('idle')
  const statusMessage = ref('')
  const aiPartialText = ref('')

  let ws: WebSocket | null = null
  let audioContext: AudioContext | null = null
  let mediaStream: MediaStream | null = null
  let workletNode: AudioWorkletNode | null = null
  // Fallback cho browsers không hỗ trợ AudioWorklet
  let processorNode: ScriptProcessorNode | null = null

  // ── Audio playback: accumulate MP3 chunks per sentence, then play ──
  let audioChunks: Uint8Array[] = []
  let audioPlayQueue: Blob[] = []
  let isPlaying = false
  // Playback AudioContext riêng — tránh conflict với capture context
  let playbackContext: AudioContext | null = null
  let currentSource: AudioBufferSourceNode | null = null

  function getVoiceWsUrl(): string {
    // Unified server — voice WS runs on same port as API
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    return `${proto}//${window.location.host}/ws/voice`
  }

  // ── Connect WebSocket ──
  function connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      if (ws && ws.readyState === WebSocket.OPEN) {
        resolve()
        return
      }

      voiceState.value = 'connecting'
      const url = getVoiceWsUrl()
      console.log('[Voice] Connecting to', url)
      ws = new WebSocket(url)

      ws.onopen = () => {
        ws!.send(JSON.stringify({ type: 'start_conversation' }))
        resolve()
      }

      ws.onmessage = (event) => {
        const msg = JSON.parse(event.data)
        handleServerMessage(msg)
      }

      ws.onerror = (err) => {
        console.error('[Voice] WebSocket error:', err)
        voiceState.value = 'error'
        statusMessage.value = 'Không thể kết nối voice server'
        reject(new Error('WebSocket connection failed'))
      }

      ws.onclose = () => {
        if (voiceState.value !== 'idle') {
          voiceState.value = 'idle'
          stopMicrophone()
        }
      }
    })
  }

  // ── Handle messages from voice server ──
  function handleServerMessage(msg: Record<string, unknown>) {
    switch (msg.type) {
      case 'conversation_started':
        voiceState.value = 'listening'
        statusMessage.value = 'Đang lắng nghe...'
        break

      case 'vad_status':
        if (msg.state === 'speech' && voiceState.value === 'listening') {
          voiceState.value = 'recording'
          statusMessage.value = 'Đang nghe bạn nói...'
        }
        break

      case 'turn_start':
        voiceState.value = 'recording'
        statusMessage.value = 'Đang nghe bạn nói...'
        break

      case 'turn_end':
        voiceState.value = 'processing'
        statusMessage.value = 'Đang xử lý...'
        break

      case 'transcript_user':
        chatStore.addMessage({
          role: 'user',
          content: msg.text as string,
          timestamp: new Date().toISOString(),
        })
        break

      case 'status':
        voiceState.value = 'processing'
        statusMessage.value = msg.message as string
        break

      case 'transcript_ai_partial':
        voiceState.value = 'speaking'
        aiPartialText.value = msg.full_text as string
        statusMessage.value = 'AI đang trả lời...'
        break

      case 'transcript_ai':
        if (msg.done) {
          chatStore.addMessage({
            role: 'assistant',
            content: msg.text as string,
            timestamp: new Date().toISOString(),
          })
          aiPartialText.value = ''
        }
        break

      case 'audio_chunk':
        accumulateAudioChunk(msg.data as string, msg.text as string | null)
        break

      case 'audio_done':
        flushAudioChunks()
        // Chuyển state sau khi audio phát xong (không ngay lập tức)
        if (audioPlayQueue.length === 0 && !isPlaying) {
          voiceState.value = 'listening'
          statusMessage.value = 'Đang lắng nghe...'
        }
        break

      case 'interrupted':
        // Dừng phát audio ngay lập tức
        audioChunks = []
        audioPlayQueue = []
        isPlaying = false
        if (currentSource) {
          try { currentSource.stop() } catch {}
          currentSource = null
        }
        voiceState.value = 'listening'
        statusMessage.value = 'Đang lắng nghe...'
        break

      case 'error':
        statusMessage.value = msg.message as string
        if (voiceState.value === 'processing') {
          voiceState.value = 'listening'
        }
        break
    }
  }

  // ── Audio playback: accumulate chunks per sentence, decode as blob ──

  function accumulateAudioChunk(base64Data: string, text: string | null) {
    const bytes = base64ToUint8Array(base64Data)
    audioChunks.push(bytes)

    if (text && audioChunks.length > 1) {
      const prev = audioChunks.slice(0, -1)
      audioChunks = [bytes]
      const blob = new Blob(prev, { type: 'audio/mpeg' })
      audioPlayQueue.push(blob)
      if (!isPlaying) {
        playNextBlob()
      }
    }
  }

  function flushAudioChunks() {
    if (audioChunks.length > 0) {
      const blob = new Blob(audioChunks, { type: 'audio/mpeg' })
      audioPlayQueue.push(blob)
      audioChunks = []
      if (!isPlaying) {
        playNextBlob()
      }
    }
  }

  async function playNextBlob() {
    if (audioPlayQueue.length === 0) {
      isPlaying = false
      currentSource = null
      // Chuyển sang listening khi phát xong tất cả audio
      if (voiceState.value === 'speaking') {
        voiceState.value = 'listening'
        statusMessage.value = 'Đang lắng nghe...'
      }
      return
    }
    isPlaying = true
    const blob = audioPlayQueue.shift()!

    try {
      if (!playbackContext) {
        playbackContext = new AudioContext()
      }
      if (playbackContext.state === 'suspended') {
        await playbackContext.resume()
      }

      const arrayBuffer = await blob.arrayBuffer()
      const audioBuffer = await playbackContext.decodeAudioData(arrayBuffer)
      const source = playbackContext.createBufferSource()
      source.buffer = audioBuffer
      source.connect(playbackContext.destination)
      currentSource = source
      source.onended = () => {
        currentSource = null
        playNextBlob()
      }
      source.start()
    } catch (err) {
      console.warn('[Voice] Audio decode error, skipping:', err)
      currentSource = null
      playNextBlob()
    }
  }

  // ── Microphone capture ──
  async function startMicrophone() {
    try {
      mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate: 16000,
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
        },
      })

      audioContext = new AudioContext({ sampleRate: 16000 })
      const source = audioContext.createMediaStreamSource(mediaStream)

      // Thử AudioWorklet trước, fallback sang ScriptProcessor
      try {
        await audioContext.audioWorklet.addModule('/audio-processor.js')
        workletNode = new AudioWorkletNode(audioContext, 'pcm-processor')
        workletNode.port.onmessage = (e: MessageEvent<ArrayBuffer>) => {
          if (!ws || ws.readyState !== WebSocket.OPEN) return
          if (voiceState.value === 'idle') return
          const base64 = arrayBufferToBase64(e.data)
          ws!.send(JSON.stringify({ type: 'audio_chunk', data: base64 }))
        }
        source.connect(workletNode)
        workletNode.connect(audioContext.destination)
        console.log('[Voice] Using AudioWorklet (recommended)')
      } catch (workletErr) {
        console.warn('[Voice] AudioWorklet not available, fallback to ScriptProcessor:', workletErr)
        processorNode = audioContext.createScriptProcessor(4096, 1, 1)
        processorNode.onaudioprocess = (e) => {
          if (!ws || ws.readyState !== WebSocket.OPEN) return
          if (voiceState.value === 'idle') return

          const float32 = e.inputBuffer.getChannelData(0)
          const int16 = new Int16Array(float32.length)
          for (let i = 0; i < float32.length; i++) {
            const s = Math.max(-1, Math.min(1, float32[i]))
            int16[i] = s < 0 ? s * 0x8000 : s * 0x7fff
          }

          const base64 = arrayBufferToBase64(int16.buffer)
          ws!.send(JSON.stringify({ type: 'audio_chunk', data: base64 }))
        }
        source.connect(processorNode)
        processorNode.connect(audioContext.destination)
      }
    } catch (err) {
      console.error('[Voice] Microphone access failed:', err)
      voiceState.value = 'error'
      statusMessage.value = 'Không thể truy cập microphone'
      throw err
    }
  }

  function stopMicrophone() {
    workletNode?.disconnect()
    workletNode = null
    processorNode?.disconnect()
    processorNode = null
    mediaStream?.getTracks().forEach((t) => t.stop())
    mediaStream = null
    if (audioContext && audioContext.state !== 'closed') {
      audioContext.close().catch(() => {})
    }
    audioContext = null
  }

  // ── Public API ──
  async function startVoice() {
    try {
      await connect()
      await startMicrophone()
    } catch {
      voiceState.value = 'error'
    }
  }

  function stopVoice() {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'stop_conversation' }))
      ws.close()
    }
    ws = null
    stopMicrophone()
    // Dừng audio playback
    if (currentSource) {
      try { currentSource.stop() } catch {}
      currentSource = null
    }
    if (playbackContext && playbackContext.state !== 'closed') {
      playbackContext.close().catch(() => {})
    }
    playbackContext = null
    audioChunks = []
    audioPlayQueue = []
    isPlaying = false
    voiceState.value = 'idle'
    statusMessage.value = ''
    aiPartialText.value = ''
  }

  function interrupt() {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'interrupt' }))
    }
  }

  onUnmounted(() => {
    stopVoice()
  })

  return {
    voiceState,
    statusMessage,
    aiPartialText,
    startVoice,
    stopVoice,
    interrupt,
  }
}

// ── Helpers ──

/**
 * Chuyển ArrayBuffer → base64 string.
 * Dùng chunked approach để tránh stack overflow với buffer lớn.
 */
function arrayBufferToBase64(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer)
  const chunkSize = 8192
  let binary = ''
  for (let i = 0; i < bytes.length; i += chunkSize) {
    const chunk = bytes.subarray(i, i + chunkSize)
    binary += String.fromCharCode(...chunk)
  }
  return btoa(binary)
}

/**
 * Chuyển base64 → Uint8Array.
 * Nhanh hơn Uint8Array.from(atob(...)) vì dùng TextEncoder-free approach.
 */
function base64ToUint8Array(base64: string): Uint8Array {
  const binary = atob(base64)
  const bytes = new Uint8Array(binary.length)
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i)
  }
  return bytes
}
