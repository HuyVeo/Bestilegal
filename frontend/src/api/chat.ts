import { authHeaders } from './client'
import { parseSSEStream, type SSECallbacks } from '@/lib/sse'
import type { ChatRequest } from '@/types/chat'

export async function streamChat(
  request: ChatRequest,
  callbacks: SSECallbacks,
  signal?: AbortSignal,
): Promise<void> {
  const resp = await fetch('/api/chat', {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify(request),
    signal,
  })

  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ error: 'Server error' }))
    throw new Error(err.error || `HTTP ${resp.status}`)
  }

  await parseSSEStream(resp, callbacks)
}
