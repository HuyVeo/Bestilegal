<script setup lang="ts">
import type { LegalArticle } from '@/types/chat'
import { Scale, Search } from 'lucide-vue-next'

defineProps<{
  article: LegalArticle
  index: number
}>()

defineEmits<{ click: [index: number] }>()
</script>

<template>
  <button
    class="flex items-center gap-2 px-3 py-2 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800
      rounded-lg hover:bg-green-100 dark:hover:bg-green-900/40 hover:border-green-300 transition-all text-left group"
    @click="$emit('click', index)"
  >
    <Scale :size="14" class="text-green-600 dark:text-green-400 flex-shrink-0" />
    <span class="text-xs font-medium text-green-800 dark:text-green-300 flex-1 truncate">
      {{ article.article ? `${article.document_name}, ${article.article}` : article.document_name }}
    </span>
    <span v-if="article.from_response" class="text-xs text-brand-blue dark:text-blue-300">
      <Search :size="12" />
    </span>
    <span v-else-if="article.score" class="text-xs font-semibold text-green-600 dark:text-green-400">
      {{ Math.round((article.score || 0) * 100) }}%
    </span>
  </button>
</template>
