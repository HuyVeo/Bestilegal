<script setup lang="ts">
import { useChatStore } from '@/stores/chat'
import { useUiStore } from '@/stores/ui'
import { extractDomain } from '@/lib/format'
import { Search, ChevronLeft, ChevronRight, ExternalLink } from 'lucide-vue-next'

const chatStore = useChatStore()
const uiStore = useUiStore()

function reliabilityClass(r: number) {
  if (r >= 0.9) return 'bg-green-500'
  if (r >= 0.7) return 'bg-yellow-500'
  return 'bg-red-400'
}
</script>

<template>
  <!-- Toggle button -->
  <button
    v-if="uiStore.hasWebResults"
    class="absolute top-1/2 -translate-y-1/2 z-20 w-6 h-14 bg-white dark:bg-gray-800 border border-border-light dark:border-gray-700 border-r-0 rounded-l-lg
      flex items-center justify-center text-text-muted hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors shadow-sm
      hidden md:flex"
    :style="{ right: uiStore.webSidebarOpen ? '320px' : '0' }"
    @click="uiStore.toggleWebSidebar()"
  >
    <ChevronLeft v-if="uiStore.webSidebarOpen" :size="14" />
    <ChevronRight v-else :size="14" />
  </button>

  <!-- Sidebar -->
  <aside
    v-if="uiStore.hasWebResults"
    :class="[
      'w-[320px] min-w-[280px] border-l border-border-light dark:border-gray-700 bg-gray-50 dark:bg-gray-900 overflow-y-auto flex-shrink-0 transition-all duration-300',
      'hidden md:block',
      uiStore.webSidebarOpen ? 'opacity-100' : 'w-0 min-w-0 opacity-0 overflow-hidden !border-l-0 !p-0'
    ]"
  >
    <div class="p-4">
      <!-- Header -->
      <div class="flex items-center gap-1.5 mb-3">
        <Search :size="14" class="text-text-muted dark:text-gray-400" />
        <span class="text-[0.82rem] font-bold text-text-muted dark:text-gray-400">
          Kết quả tìm kiếm web ({{ chatStore.webResults.length }})
        </span>
      </div>

      <!-- Results -->
      <div class="flex flex-col divide-y divide-gray-200 dark:divide-gray-700">
        <div v-for="(w, i) in chatStore.webResults" :key="i" class="py-2.5">
          <a
            :href="w.url"
            target="_blank"
            rel="noopener noreferrer"
            class="text-[0.8rem] font-semibold text-text-body dark:text-gray-300 hover:text-brand-blue dark:hover:text-blue-300 block mb-1 leading-snug group"
          >
            {{ w.title || extractDomain(w.url) }}
            <ExternalLink :size="11" class="inline-block ml-1 opacity-0 group-hover:opacity-100 transition-opacity" />
          </a>
          <div class="flex items-center gap-1.5 text-[0.68rem] text-text-light dark:text-gray-500">
            <span
              :class="['w-[7px] h-[7px] rounded-full', reliabilityClass(w.reliability || 0)]"
            />
            <span class="text-green-700 dark:text-green-400 font-medium">
              {{ extractDomain(w.url) }}
            </span>
            <span v-if="w.publish_date" class="text-text-muted dark:text-gray-500">
              {{ w.publish_date }}
            </span>
          </div>
        </div>
      </div>
    </div>
  </aside>
</template>
