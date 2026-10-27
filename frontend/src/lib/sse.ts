import type { SSEEvent } from '@/types/chat'

export interface SSECallbacks {
  onChunk: (text: string) => void
  onDone: (event: SSEEvent) => void
  onError: (error: string) => void
}

export async function parseSSEStream(
  response: Response,
  callbacks: SSECallbacks,
): Promise<void> {
  const reader = response.body!.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop()!

    for (const line of lines) {
      if (!line.startsWith('data: ')) continue
      const raw = line.slice(6).trim()
      if (!raw) continue

      try {
        const event: SSEEvent = JSON.parse(raw)
        if (event.type === 'chunk') callbacks.onChunk(event.content ?? '')
        else if (event.type === 'done') callbacks.onDone(event)
        else if (event.type === 'error') callbacks.onError(event.content ?? 'Unknown error')
      } catch {
        /* skip malformed JSON */
      }
    }
  }
}
