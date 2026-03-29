import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as convApi from '@/api/conversations'
import type { Conversation } from '@/types/conversation'

export const useConversationsStore = defineStore('conversations', () => {
  const conversations = ref<Conversation[]>([])
  const loading = ref(false)
  const total = ref(0)

  async function fetchConversations() {
    loading.value = true
    try {
      const data = await convApi.listConversations()
      // Backend returns plain array or {conversations: [...]}
      if (Array.isArray(data)) {
        conversations.value = data
        total.value = data.length
      } else {
        conversations.value = data.conversations || []
        total.value = data.total || 0
      }
    } catch {
      /* ignore */
    } finally {
      loading.value = false
    }
  }

  async function rename(id: string, title: string) {
    await convApi.renameConversation(id, title)
    const conv = conversations.value.find(c => c.id === id)
    if (conv) conv.title = title
  }

  async function remove(id: string) {
    await convApi.deleteConversation(id)
    conversations.value = conversations.value.filter(c => c.id !== id)
  }

  return {
    conversations,
    loading,
    total,
    fetchConversations,
    rename,
    remove,
  }
})
