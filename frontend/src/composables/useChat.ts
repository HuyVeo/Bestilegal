import { ref } from 'vue'
import { streamChat } from '@/api/chat'
import { useChatStore } from '@/stores/chat'
import { useConversationsStore } from '@/stores/conversations'
import { useUiStore } from '@/stores/ui'
import type { SSEEvent } from '@/types/chat'

export function useChat() {
  const chatStore = useChatStore()
  const convStore = useConversationsStore()
  const uiStore = useUiStore()
  const abortController = ref<AbortController | null>(null)

  async function sendMessage(question: string) {
    if (!question.trim() || chatStore.isStreaming) return

    chatStore.isStreaming = true
    chatStore.streamingText = ''
    chatStore.legalBasis = []
    chatStore.webResults = []
    chatStore.suggestions = []

    chatStore.addMessage({
      role: 'user',
      content: question,
      timestamp: new Date().toISOString(),
    })

    abortController.value = new AbortController()

    try {
      await streamChat(
        {
          question,
          messages: chatStore.messages.slice(0, -1),
          conv_id: chatStore.convId,
        },
        {
          onChunk(text: string) {
            chatStore.appendStreamingText(text)
          },
          onDone(event: SSEEvent) {
            const finalResponse = event.final_response || chatStore.streamingText
            chatStore.finalizeAssistantMessage(finalResponse, event.sources || [])
            chatStore.setDoneData({
              conv_id: event.conv_id!,
              legal_basis: event.legal_basis || [],
              web_results: event.web_results || [],
              sources: event.sources || [],
              suggestions: event.suggestions || [],
              warnings: event.warnings || [],
            })

            if ((event.web_results || []).length > 0) {
              uiStore.hasWebResults = true
              uiStore.webSidebarOpen = true
            }

            convStore.fetchConversations()
          },
          onError(error: string) {
            chatStore.streamingText = ''
            chatStore.addMessage({
              role: 'assistant',
              content: `Error: ${error}`,
              timestamp: new Date().toISOString(),
            })
          },
        },
        abortController.value.signal,
      )
    } catch (e: unknown) {
      if ((e as Error).name !== 'AbortError') {
        chatStore.streamingText = ''
        chatStore.addMessage({
          role: 'assistant',
          content: `Error: ${(e as Error).message}`,
          timestamp: new Date().toISOString(),
        })
      }
    } finally {
      chatStore.isStreaming = false
      abortController.value = null
    }
  }

  function stopStreaming() {
    abortController.value?.abort()
  }

  async function retryLastMessage() {
    const msgs = chatStore.messages
    if (msgs.length < 2) return
    // Remove last assistant message
    const lastAssistant = msgs[msgs.length - 1]
    if (lastAssistant.role === 'assistant') {
      msgs.pop()
    }
    // Get last user message
    const lastUser = msgs[msgs.length - 1]
    if (lastUser?.role === 'user') {
      msgs.pop()
      await sendMessage(lastUser.content)
    }
  }

  return {
    sendMessage,
    stopStreaming,
    retryLastMessage,
  }
}
