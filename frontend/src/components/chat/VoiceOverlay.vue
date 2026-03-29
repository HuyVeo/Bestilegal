<script setup lang="ts">
import { MicOff, Mic, Loader2, Volume2 } from 'lucide-vue-next'
import type { VoiceState } from '@/composables/useVoiceChat'

defineProps<{
  voiceState: VoiceState
  statusMessage: string
  aiPartialText: string
}>()

defineEmits<{
  stop: []
}>()
</script>

<template>
  <div class="mx-4 mb-2">
    <div class="max-w-3xl mx-auto bg-gradient-to-r rounded-2xl px-5 py-4 shadow-lg border transition-all"
      :class="{
        'from-blue-50 to-indigo-50 dark:from-blue-950/40 dark:to-indigo-950/40 border-blue-200 dark:border-blue-800': voiceState === 'listening',
        'from-green-50 to-emerald-50 dark:from-green-950/40 dark:to-emerald-950/40 border-green-300 dark:border-green-800': voiceState === 'recording',
        'from-amber-50 to-orange-50 dark:from-amber-950/40 dark:to-orange-950/40 border-amber-200 dark:border-amber-800': voiceState === 'processing',
        'from-purple-50 to-pink-50 dark:from-purple-950/40 dark:to-pink-950/40 border-purple-200 dark:border-purple-800': voiceState === 'speaking',
        'from-red-50 to-rose-50 dark:from-red-950/40 dark:to-rose-950/40 border-red-200 dark:border-red-800': voiceState === 'error',
        'from-gray-50 to-slate-50 dark:from-gray-900 dark:to-slate-900 border-gray-200 dark:border-gray-700': voiceState === 'connecting',
      }"
    >
      <div class="flex items-center gap-3">
        <!-- Status icon -->
        <div class="w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0"
          :class="{
            'bg-blue-100 dark:bg-blue-900 text-blue-600 dark:text-blue-400 listening-pulse': voiceState === 'listening',
            'bg-green-100 dark:bg-green-900 text-green-600 dark:text-green-400 recording-pulse': voiceState === 'recording',
            'bg-amber-100 dark:bg-amber-900 text-amber-600 dark:text-amber-400': voiceState === 'processing',
            'bg-purple-100 dark:bg-purple-900 text-purple-600 dark:text-purple-400': voiceState === 'speaking',
            'bg-red-100 dark:bg-red-900 text-red-600 dark:text-red-400': voiceState === 'error',
            'bg-gray-100 dark:bg-gray-800 text-gray-500': voiceState === 'connecting',
          }"
        >
          <Mic v-if="voiceState === 'listening'" :size="20" />
          <Mic v-else-if="voiceState === 'recording'" :size="20" />
          <Loader2 v-else-if="voiceState === 'processing' || voiceState === 'connecting'" :size="20" class="animate-spin" />
          <Volume2 v-else-if="voiceState === 'speaking'" :size="20" />
          <Mic v-else :size="20" />
        </div>

        <!-- Status text -->
        <div class="flex-1 min-w-0">
          <p class="text-sm font-medium text-gray-700 dark:text-gray-200">
            {{ statusMessage || 'Voice chat' }}
          </p>
          <p v-if="aiPartialText" class="text-xs text-gray-500 dark:text-gray-400 truncate mt-0.5">
            {{ aiPartialText.slice(-100) }}
          </p>
        </div>

        <!-- Stop button -->
        <button
          class="w-8 h-8 flex items-center justify-center rounded-lg bg-red-100 dark:bg-red-900/50 text-red-600 dark:text-red-400
            hover:bg-red-200 dark:hover:bg-red-900 transition-colors flex-shrink-0"
          title="Dừng voice chat"
          @click="$emit('stop')"
        >
          <MicOff :size="16" />
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.listening-pulse {
  animation: listening 2s ease-in-out infinite;
}

.recording-pulse {
  animation: recording 0.8s ease-in-out infinite;
}

@keyframes listening {
  0%, 100% { box-shadow: 0 0 0 0 rgba(59, 130, 246, 0.3); }
  50% { box-shadow: 0 0 0 6px rgba(59, 130, 246, 0); }
}

@keyframes recording {
  0%, 100% { box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.4); transform: scale(1); }
  50% { box-shadow: 0 0 0 8px rgba(34, 197, 94, 0); transform: scale(1.05); }
}
</style>
