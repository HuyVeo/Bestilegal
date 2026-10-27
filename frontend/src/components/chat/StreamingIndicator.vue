<script setup lang="ts">
import MarkdownContent from './MarkdownContent.vue'
import BaseAvatar from '@/components/ui/BaseAvatar.vue'

defineProps<{
  text: string
  showAnalyzing: boolean
}>()
</script>

<template>
  <div class="flex items-end gap-2.5 px-4 py-1.5 animate-fade-up">
    <BaseAvatar initials="BS" variant="white" size="sm" />

    <div class="max-w-[68%] rounded-2xl rounded-bl-md px-4 py-3 bg-white dark:bg-gray-800 border border-border-light dark:border-gray-700 shadow-sm">
      <!-- Analyzing status -->
      <div v-if="showAnalyzing && !text" class="flex items-center gap-2">
        <div class="flex items-center gap-1">
          <div class="w-1.5 h-1.5 rounded-full bg-brand-blue animate-pulse" />
          <div class="w-1.5 h-1.5 rounded-full bg-accent-red animate-pulse" style="animation-delay: 0.2s" />
          <div class="w-1.5 h-1.5 rounded-full bg-accent-yellow animate-pulse" style="animation-delay: 0.4s" />
        </div>
        <span class="text-sm text-text-muted dark:text-gray-400">Đang phân tích...</span>
      </div>

      <!-- Streaming content -->
      <MarkdownContent v-if="text" :content="text" />

      <!-- Typing dots when streaming but waiting for next chunk -->
      <div v-if="text" class="flex items-center gap-1 mt-2">
        <div class="typing-dot" />
        <div class="typing-dot" />
        <div class="typing-dot" />
      </div>
    </div>
  </div>
</template>
