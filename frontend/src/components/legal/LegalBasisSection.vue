<script setup lang="ts">
import { ref } from 'vue'
import type { LegalArticle } from '@/types/chat'
import LegalArticleChip from './LegalArticleChip.vue'
import LegalArticlePanel from './LegalArticlePanel.vue'
import { Scale } from 'lucide-vue-next'

defineProps<{
  articles: LegalArticle[]
}>()

const selectedIndex = ref<number | null>(null)

function showArticle(index: number) {
  selectedIndex.value = index
}
</script>

<template>
  <div class="border-t border-border-light dark:border-gray-700 pt-3 mt-1">
    <div class="flex items-center gap-1.5 mb-2">
      <Scale :size="14" class="text-green-600 dark:text-green-400" />
      <span class="text-xs font-bold text-green-700 dark:text-green-300 uppercase tracking-wide">Căn cứ pháp lý</span>
    </div>
    <div class="flex flex-wrap gap-1.5">
      <LegalArticleChip
        v-for="(art, i) in articles"
        :key="i"
        :article="art"
        :index="i"
        @click="showArticle"
      />
    </div>
  </div>

  <!-- Article detail panel -->
  <LegalArticlePanel
    v-if="selectedIndex !== null"
    :article="articles[selectedIndex]"
    @close="selectedIndex = null"
  />
</template>
