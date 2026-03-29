import { computed } from 'vue'
import { useUiStore } from '@/stores/ui'

export function useTheme() {
  const uiStore = useUiStore()

  const isDark = computed(() => uiStore.theme === 'dark')

  function toggle() {
    uiStore.toggleTheme()
  }

  return { isDark, toggle }
}
