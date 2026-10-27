<script setup lang="ts">
import { computed, onMounted, ref, watch, nextTick } from 'vue'
import { renderMarkdown } from '@/lib/markdown'

const props = defineProps<{
  content: string
}>()

const containerRef = ref<HTMLElement | null>(null)
const html = computed(() => renderMarkdown(props.content))

function addCopyButtons() {
  if (!containerRef.value) return
  containerRef.value.querySelectorAll('pre').forEach((pre) => {
    if (pre.querySelector('.copy-btn')) return
    const btn = document.createElement('button')
    btn.className = 'copy-btn absolute top-2 right-2 px-2 py-1 text-xs text-gray-400 hover:text-white bg-gray-800 rounded-md transition-colors'
    btn.textContent = 'Copy'
    btn.onclick = () => {
      const code = pre.querySelector('code')?.textContent || ''
      navigator.clipboard.writeText(code).then(() => {
        btn.textContent = 'Copied!'
        setTimeout(() => { btn.textContent = 'Copy' }, 2000)
      })
    }
    pre.style.position = 'relative'
    pre.appendChild(btn)
  })
}

onMounted(addCopyButtons)
watch(html, () => nextTick(addCopyButtons))
</script>

<template>
  <div ref="containerRef" class="prose-chat" v-html="html" />
</template>
