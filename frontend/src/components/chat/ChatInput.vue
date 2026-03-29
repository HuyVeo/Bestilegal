<script setup lang="ts">
import { ref } from 'vue'
import { useChatStore } from '@/stores/chat'
import { useAutoResize } from '@/composables/useAutoResize'
import { Send, Square, Mic, MicOff } from 'lucide-vue-next'
import type { VoiceState } from '@/composables/useVoiceChat'

const props = defineProps<{
  voiceState?: VoiceState
}>()

const emit = defineEmits<{
  send: [question: string]
  'voice-start': []
  'voice-stop': []
}>()

const chatStore = useChatStore()

const input = ref('')
const textareaRef = ref<HTMLTextAreaElement | null>(null)
const { resize } = useAutoResize(textareaRef)

function handleSend() {
  const q = input.value.trim()
  if (!q || chatStore.isStreaming) return
  emit('send', q)
  input.value = ''
  if (textareaRef.value) {
    textareaRef.value.style.height = 'auto'
  }
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSend()
  }
}

function toggleVoice() {
  if (props.voiceState && props.voiceState !== 'idle') {
    emit('voice-stop')
  } else {
    emit('voice-start')
  }
}
</script>

<template>
  <div class="px-4 pb-4 pt-2">
    <div class="max-w-3xl mx-auto relative">
      <div class="flex items-end gap-2 bg-white dark:bg-gray-800 border border-border-light dark:border-gray-700 rounded-2xl px-4 py-3
        shadow-lg focus-within:ring-2 focus-within:ring-brand-blue/20 focus-within:border-brand-blue transition-all">
        <textarea
          ref="textareaRef"
          v-model="input"
          rows="1"
          placeholder="Nhập câu hỏi..."
          class="flex-1 resize-none bg-transparent text-sm text-text-body dark:text-gray-200 placeholder:text-text-light dark:placeholder:text-gray-500
            outline-none font-medium leading-relaxed max-h-[150px]"
          @keydown="handleKeydown"
          @input="resize"
        />

        <!-- Voice button -->
        <button
          class="w-9 h-9 flex items-center justify-center rounded-xl transition-colors flex-shrink-0"
          :class="voiceState && voiceState !== 'idle'
            ? 'bg-accent-red text-white hover:bg-red-700 voice-active'
            : 'bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-600 hover:text-brand-blue'"
          :title="voiceState && voiceState !== 'idle' ? 'Dừng voice' : 'Nói chuyện'"
          @click="toggleVoice"
        >
          <MicOff v-if="voiceState && voiceState !== 'idle'" :size="16" />
          <Mic v-else :size="16" />
        </button>

        <!-- Stop streaming button -->
        <button
          v-if="chatStore.isStreaming"
          class="w-9 h-9 flex items-center justify-center rounded-xl bg-accent-red text-white hover:bg-red-700 transition-colors flex-shrink-0"
          title="Dừng"
          @click="$emit('send', '__stop__')"
        >
          <Square :size="16" fill="currentColor" />
        </button>
        <!-- Send button -->
        <button
          v-else
          :disabled="!input.trim()"
          class="w-9 h-9 flex items-center justify-center rounded-xl bg-brand-blue text-white
            hover:bg-brand-blue-light disabled:opacity-30 disabled:cursor-not-allowed transition-colors flex-shrink-0"
          @click="handleSend"
        >
          <Send :size="16" />
        </button>
      </div>
      <p class="text-center text-[0.68rem] text-text-light dark:text-gray-500 mt-2">
        Enter để gửi, Shift+Enter để xuống dòng
      </p>
    </div>
  </div>
</template>

<style scoped>
.voice-active {
  animation: pulse-voice 1.5s ease-in-out infinite;
}

@keyframes pulse-voice {
  0%, 100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.4); }
  50% { box-shadow: 0 0 0 8px rgba(239, 68, 68, 0); }
}
</style>
