<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import type { LegalArticle } from '@/types/chat'
import { cleanLegalArticle } from '@/api/legal'
import MarkdownContent from '@/components/chat/MarkdownContent.vue'
import BaseSpinner from '@/components/ui/BaseSpinner.vue'
import { X, Scale } from 'lucide-vue-next'

const props = defineProps<{
  article: LegalArticle
}>()

defineEmits<{ close: [] }>()

const cleanedContent = ref('')
const loading = ref(false)

// Cache for cleaned articles
const cache = new Map<string, string>()

const label = computed(() =>
  props.article.article
    ? `${props.article.document_name}, ${props.article.article}`
    : props.article.document_name
)

const rawContent = computed(() =>
  props.article.content || props.article.snippet || 'Không có nội dung chi tiết.'
)

const isFromRAG = computed(() =>
  !props.article.from_response && rawContent.value.length > 100
)

onMounted(async () => {
  if (!isFromRAG.value) {
    cleanedContent.value = rawContent.value
    return
  }

  const cacheKey = `${props.article.document_name}|${props.article.article}|${rawContent.value.length}`
  if (cache.has(cacheKey)) {
    cleanedContent.value = cache.get(cacheKey)!
    return
  }

  loading.value = true
  try {
    const data = await cleanLegalArticle({
      content: rawContent.value,
      document_name: props.article.document_name || '',
      article: props.article.article || '',
    })
    cleanedContent.value = data.cleaned || rawContent.value
    cache.set(cacheKey, cleanedContent.value)
  } catch {
    cleanedContent.value = rawContent.value
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <Teleport to="body">
    <div class="fixed inset-0 z-50 flex justify-end" @click.self="$emit('close')">
      <div class="absolute inset-0 bg-black/30 backdrop-blur-sm" @click="$emit('close')" />

      <div class="relative w-full max-w-lg bg-white dark:bg-gray-800 shadow-2xl animate-slide-in-right flex flex-col">
        <!-- Header -->
        <div class="flex items-center gap-3 px-5 py-4 border-b border-border-light dark:border-gray-700 flex-shrink-0">
          <Scale :size="20" class="text-green-600 dark:text-green-400 flex-shrink-0" />
          <h3 class="text-base font-heading font-bold text-text-primary dark:text-gray-100 flex-1 truncate">
            {{ label }}
          </h3>
          <button
            class="w-8 h-8 flex items-center justify-center rounded-lg text-text-muted hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
            @click="$emit('close')"
          >
            <X :size="18" />
          </button>
        </div>

        <!-- Body -->
        <div class="flex-1 overflow-y-auto px-5 py-4">
          <div v-if="loading" class="flex items-center justify-center gap-2 py-12">
            <BaseSpinner size="sm" />
            <span class="text-sm text-text-muted dark:text-gray-400">Đang định dạng nội dung điều luật...</span>
          </div>
          <MarkdownContent v-else :content="cleanedContent" />
        </div>
      </div>
    </div>
  </Teleport>
</template>
