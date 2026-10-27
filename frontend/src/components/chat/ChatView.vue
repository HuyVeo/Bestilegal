<script setup lang="ts">
import { computed } from 'vue'
import { useChatStore } from '@/stores/chat'
import { useChat } from '@/composables/useChat'
import { useVoiceChat } from '@/composables/useVoiceChat'
import WelcomeScreen from './WelcomeScreen.vue'
import MessageList from './MessageList.vue'
import ChatInput from './ChatInput.vue'
import VoiceOverlay from './VoiceOverlay.vue'
import WebResultsSidebar from '@/components/legal/WebResultsSidebar.vue'

const chatStore = useChatStore()
const { sendMessage, stopStreaming, retryLastMessage } = useChat()
const { voiceState, statusMessage, aiPartialText, startVoice, stopVoice } = useVoiceChat()

const hasMessages = computed(() => chatStore.messages.length > 0 || chatStore.isStreaming)

function handleSend(question: string) {
  if (question === '__stop__') {
    stopStreaming()
    return
  }
  sendMessage(question)
}
</script>

<template>
  <div class="flex h-full overflow-hidden">
    <!-- Main chat area -->
    <div class="flex-1 flex flex-col min-w-0">
      <WelcomeScreen v-if="!hasMessages" @ask="sendMessage" />
      <MessageList v-else @ask="sendMessage" @retry="retryLastMessage" />

      <!-- Voice overlay -->
      <VoiceOverlay
        v-if="voiceState !== 'idle'"
        :voice-state="voiceState"
        :status-message="statusMessage"
        :ai-partial-text="aiPartialText"
        @stop="stopVoice"
      />

      <ChatInput
        :voice-state="voiceState"
        @send="handleSend"
        @voice-start="startVoice"
        @voice-stop="stopVoice"
      />
    </div>

    <!-- Web results sidebar -->
    <WebResultsSidebar />
  </div>
</template>
