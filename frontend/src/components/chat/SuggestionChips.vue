<script setup lang="ts">
import { Lightbulb } from 'lucide-vue-next'

defineProps<{
  suggestions: string[]
  label?: string
}>()

defineEmits<{ ask: [question: string] }>()
</script>

<template>
  <div v-if="suggestions.length" class="px-4 py-2 max-w-3xl mx-auto">
    <div class="flex items-center gap-1.5 mb-2" v-if="label">
      <Lightbulb :size="14" class="text-accent-yellow" />
      <span class="text-xs font-semibold text-text-muted dark:text-gray-400">{{ label }}</span>
    </div>
    <div class="flex flex-wrap gap-2">
      <button
        v-for="s in suggestions"
        :key="s"
        class="px-3.5 py-2 text-sm text-brand-blue dark:text-blue-300 bg-blue-50 dark:bg-blue-900/20
          rounded-xl border border-blue-200 dark:border-blue-800
          hover:bg-blue-100 dark:hover:bg-blue-900/40 hover:border-blue-300
          transition-all duration-200 text-left leading-snug"
        @click="$emit('ask', s)"
      >
        {{ s }}
      </button>
    </div>
  </div>
</template>
