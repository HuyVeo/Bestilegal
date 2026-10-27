import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Message, LegalArticle, WebResult, Source } from '@/types/chat'

export const useChatStore = defineStore('chat', () => {
  const convId = ref<string | null>(null)
  const messages = ref<Message[]>([])
  const isStreaming = ref(false)
  const streamingText = ref('')
  const sources = ref<Source[]>([])
  const legalBasis = ref<LegalArticle[]>([])
  const webResults = ref<WebResult[]>([])
  const suggestions = ref<string[]>([])
  const warnings = ref<string[]>([])
  const defaultSuggestions = ref<string[]>([])

  function addMessage(msg: Message) {
    messages.value.push(msg)
  }

  function appendStreamingText(text: string) {
    streamingText.value += text
  }

  function finalizeAssistantMessage(finalResponse: string, msgSources: Source[]) {
    streamingText.value = ''
    messages.value.push({
      role: 'assistant',
      content: finalResponse,
      sources: msgSources,
      timestamp: new Date().toISOString(),
    })
  }

  function setDoneData(data: {
    conv_id: string
    legal_basis: LegalArticle[]
    web_results: WebResult[]
    sources: Source[]
    suggestions: string[]
    warnings: string[]
  }) {
    convId.value = data.conv_id
    legalBasis.value = data.legal_basis
    webResults.value = data.web_results
    sources.value = data.sources
    suggestions.value = data.suggestions
    warnings.value = data.warnings
  }

  function startNewChat() {
    convId.value = null
    messages.value = []
    streamingText.value = ''
    isStreaming.value = false
    sources.value = []
    legalBasis.value = []
    webResults.value = []
    suggestions.value = []
    warnings.value = []
  }

  function loadConversation(id: string, msgs: Message[]) {
    convId.value = id
    messages.value = msgs
    streamingText.value = ''
    isStreaming.value = false
    sources.value = []
    legalBasis.value = []
    webResults.value = []
    suggestions.value = []
    warnings.value = []
  }

  return {
    convId,
    messages,
    isStreaming,
    streamingText,
    sources,
    legalBasis,
    webResults,
    suggestions,
    warnings,
    defaultSuggestions,
    addMessage,
    appendStreamingText,
    finalizeAssistantMessage,
    setDoneData,
    startNewChat,
    loadConversation,
  }
})
