import { onMounted, onBeforeUnmount, type Ref } from 'vue'

export function useAutoResize(textareaRef: Ref<HTMLTextAreaElement | null>, maxHeight = 150) {
  function resize() {
    const el = textareaRef.value
    if (!el) return
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, maxHeight) + 'px'
  }

  onMounted(() => {
    textareaRef.value?.addEventListener('input', resize)
  })

  onBeforeUnmount(() => {
    textareaRef.value?.removeEventListener('input', resize)
  })

  return { resize }
}
