<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useChatStore } from '@/stores/chat'
import { getDefaultSuggestions } from '@/api/health'
import { Scale, Globe, TrendingUp, BookOpen } from 'lucide-vue-next'

const emit = defineEmits<{ ask: [question: string] }>()
const chatStore = useChatStore()
const subtitle = ref('')
const typingDone = ref(false)

const fullText = 'Trợ lý AI thông minh của Basao – tư vấn, hỗ trợ và trả lời mọi thắc mắc của bạn nhanh chóng và chính xác.'

const features = [
  { icon: Scale, label: 'Tư vấn pháp lý BĐS', desc: 'Luật đất đai, nhà ở, kinh doanh' },
  { icon: Globe, label: 'Tra cứu văn bản', desc: 'Hệ thống pháp luật cập nhật' },
  { icon: TrendingUp, label: 'Giá cổ phiếu', desc: 'BĐS niêm yết realtime' },
  { icon: BookOpen, label: 'Thủ tục hành chính', desc: 'Hướng dẫn chi tiết từng bước' },
]

onMounted(async () => {
  // Typing effect
  let i = 0
  const timer = setInterval(() => {
    subtitle.value += fullText[i]
    i++
    if (i >= fullText.length) {
      clearInterval(timer)
      typingDone.value = true
    }
  }, 28)

  // Load default suggestions
  try {
    const data = await getDefaultSuggestions()
    chatStore.defaultSuggestions = data.suggestions || []
  } catch { /* ignore */ }
})
</script>

<template>
  <div class="flex-1 flex flex-col items-center justify-center px-6 py-12 text-center gap-5 animate-fade-up">
    <!-- Star cluster -->
    <svg class="w-20 h-20 mb-2" viewBox="0 0 80 80" fill="none">
      <polygon points="40,4 50,28 76,28 56,46 64,72 40,56 16,72 24,46 4,28 30,28"
        fill="none" stroke="#003366" stroke-width="2.5" />
      <polygon points="40,16 46,32 64,32 50,42 55,58 40,48 25,58 30,42 16,32 34,32"
        fill="#FFD700" opacity="0.2" />
      <circle cx="40" cy="38" r="4" fill="#0055AA" opacity="0.6" />
    </svg>

    <h1 class="font-heading font-extrabold text-4xl text-navy dark:text-white tracking-wide leading-tight">
      Xin chào! <span class="text-brand-blue">Basao</span> đây
    </h1>

    <p
      :class="['text-text-muted dark:text-gray-400 text-[0.93rem] max-w-[440px] leading-relaxed min-h-[2.8em]',
        typingDone ? 'typing-done' : 'typing-cursor']"
    >
      {{ subtitle }}
    </p>

    <!-- Feature chips -->
    <div class="grid grid-cols-2 gap-3 max-w-[560px] w-full mt-2">
      <div
        v-for="f in features"
        :key="f.label"
        class="bg-white dark:bg-gray-800 border border-border-light dark:border-gray-700 rounded-xl p-4 shadow-sm
          hover:border-brand-blue hover:shadow-md hover:-translate-y-0.5 transition-all duration-200 cursor-default text-left"
      >
        <component :is="f.icon" :size="24" class="text-brand-blue mb-2" />
        <p class="text-sm font-semibold text-text-primary dark:text-gray-200">{{ f.label }}</p>
        <p class="text-xs text-text-muted dark:text-gray-400 mt-0.5">{{ f.desc }}</p>
      </div>
    </div>

    <!-- Default suggestions -->
    <div v-if="chatStore.defaultSuggestions.length" class="flex flex-wrap justify-center gap-2 mt-3 max-w-[560px]">
      <button
        v-for="s in chatStore.defaultSuggestions"
        :key="s"
        class="px-4 py-2 text-sm text-brand-blue bg-blue-50 dark:bg-blue-900/20 dark:text-blue-300
          rounded-full border border-blue-200 dark:border-blue-800
          hover:bg-blue-100 dark:hover:bg-blue-900/40 transition-colors"
        @click="emit('ask', s)"
      >
        {{ s }}
      </button>
    </div>
  </div>
</template>
