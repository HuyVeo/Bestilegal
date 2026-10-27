<script setup lang="ts">
import { ref } from 'vue'
import { Copy, Check, RotateCcw } from 'lucide-vue-next'

defineProps<{
  content: string
}>()

const emit = defineEmits<{ retry: [] }>()
const copied = ref(false)

function copyMessage(content: string) {
  const textEl = document.createElement('div')
  textEl.innerHTML = content
  const plainText = textEl.textContent || textEl.innerText || content

  navigator.clipboard.writeText(plainText).then(() => {
    copied.value = true
    setTimeout(() => { copied.value = false }, 2000)
  }).catch(() => {
    // Fallback
    const ta = document.createElement('textarea')
    ta.value = plainText
    ta.style.cssText = 'position:fixed;left:-9999px'
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    document.body.removeChild(ta)
    copied.value = true
    setTimeout(() => { copied.value = false }, 2000)
  })
}
</script>

<template>
  <div class="flex items-center gap-1 pt-1">
    <button
      class="flex items-center gap-1 px-2 py-1 text-xs text-text-muted dark:text-gray-400 hover:text-brand-blue dark:hover:text-blue-300 hover:bg-blue-50 dark:hover:bg-blue-900/20 rounded-lg transition-colors"
      @click="copyMessage(content)"
    >
      <Check v-if="copied" :size="13" class="text-green-500" />
      <Copy v-else :size="13" />
      {{ copied ? 'Đã copy' : 'Copy' }}
    </button>
    <button
      class="flex items-center gap-1 px-2 py-1 text-xs text-text-muted dark:text-gray-400 hover:text-brand-blue dark:hover:text-blue-300 hover:bg-blue-50 dark:hover:bg-blue-900/20 rounded-lg transition-colors"
      @click="emit('retry')"
    >
      <RotateCcw :size="13" />
      Trả lời lại
    </button>
  </div>
</template>
