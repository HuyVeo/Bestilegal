<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { getSharedConversation } from '@/api/conversations'
import type { Conversation } from '@/types/conversation'
import MarkdownContent from '@/components/chat/MarkdownContent.vue'
import BaseAvatar from '@/components/ui/BaseAvatar.vue'
import BaseSpinner from '@/components/ui/BaseSpinner.vue'

const route = useRoute()
const conversation = ref<Conversation | null>(null)
const loading = ref(true)
const error = ref('')

onMounted(async () => {
  try {
    const token = route.params.token as string
    conversation.value = await getSharedConversation(token)
  } catch (e: unknown) {
    error.value = (e as Error).message || 'Không tìm thấy hội thoại'
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="h-full flex flex-col">
    <!-- Header -->
    <div class="px-6 py-4 border-b border-border-light dark:border-gray-700 flex-shrink-0 bg-white dark:bg-gray-800">
      <div class="flex items-center gap-2.5">
        <svg class="w-7 h-7" viewBox="0 0 40 40" fill="none">
          <polygon points="20,2 25,14 38,14 28,23 32,36 20,28 8,36 12,23 2,14 15,14"
            fill="none" stroke="#FFD700" stroke-width="2.5" />
        </svg>
        <div>
          <h1 class="font-heading font-bold text-text-primary dark:text-gray-100">BASAO Shared Chat</h1>
          <p v-if="conversation" class="text-xs text-text-muted dark:text-gray-400">{{ conversation.title }}</p>
        </div>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="flex-1 flex items-center justify-center">
      <BaseSpinner size="lg" />
    </div>

    <!-- Error -->
    <div v-else-if="error" class="flex-1 flex items-center justify-center">
      <p class="text-accent-red text-lg">{{ error }}</p>
    </div>

    <!-- Messages -->
    <div v-else class="flex-1 overflow-y-auto py-6 star-pattern">
      <div class="max-w-3xl mx-auto flex flex-col gap-2">
        <div
          v-for="(msg, i) in conversation?.messages"
          :key="i"
          :class="['flex items-end gap-2.5 px-4 py-1.5', msg.role === 'user' ? 'justify-end' : 'justify-start']"
        >
          <BaseAvatar v-if="msg.role === 'assistant'" initials="BS" variant="white" size="sm" />
          <div :class="[
            'max-w-[68%] rounded-2xl px-4 py-3 shadow-sm',
            msg.role === 'user'
              ? 'bg-brand-blue text-white rounded-br-md'
              : 'bg-white dark:bg-gray-800 border border-border-light dark:border-gray-700 rounded-bl-md'
          ]">
            <p v-if="msg.role === 'user'" class="text-sm whitespace-pre-wrap">{{ msg.content }}</p>
            <MarkdownContent v-else :content="msg.content" />
          </div>
          <BaseAvatar v-if="msg.role === 'user'" initials="U" variant="blue" size="sm" />
        </div>
      </div>
    </div>
  </div>
</template>
