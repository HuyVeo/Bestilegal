<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import { useChatStore } from '@/stores/chat'
import MessageBubble from './MessageBubble.vue'
import StreamingIndicator from './StreamingIndicator.vue'
import SuggestionChips from './SuggestionChips.vue'

const emit = defineEmits<{ ask: [question: string]; retry: [] }>()
const chatStore = useChatStore()
const containerRef = ref<HTMLElement | null>(null)

function scrollBottom() {
  nextTick(() => {
    if (containerRef.value) {
      containerRef.value.scrollTop = containerRef.value.scrollHeight
    }
  })
}

// Auto-scroll on new messages and streaming
watch(() => chatStore.messages.length, scrollBottom)
watch(() => chatStore.streamingText, scrollBottom)
</script>

<template>
  <div ref="containerRef" class="flex-1 overflow-y-auto py-6 star-pattern">
    <div class="max-w-3xl mx-auto flex flex-col gap-1">
      <MessageBubble
        v-for="(msg, i) in chatStore.messages"
        :key="i"
        :message="msg"
        :legal-basis="i === chatStore.messages.length - 1 && msg.role === 'assistant' ? chatStore.legalBasis : undefined"
        :is-last="i === chatStore.messages.length - 1"
        @retry="emit('retry')"
      />

      <!-- Streaming bubble -->
      <StreamingIndicator
        v-if="chatStore.isStreaming"
        :text="chatStore.streamingText"
        :show-analyzing="true"
      />

      <!-- Post-response suggestions -->
      <SuggestionChips
        v-if="!chatStore.isStreaming && chatStore.suggestions.length > 0"
        :suggestions="chatStore.suggestions"
        label="Có thể bạn muốn hỏi tiếp:"
        @ask="emit('ask', $event)"
      />
    </div>
  </div>
</template>
