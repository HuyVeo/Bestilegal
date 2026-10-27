import { defineStore } from 'pinia'
import { ref, watch } from 'vue'
import { storage } from '@/lib/storage'

export const useUiStore = defineStore('ui', () => {
  const sidebarOpen = ref(window.innerWidth > 720)
  const webSidebarOpen = ref(false)
  const hasWebResults = ref(false)
  const theme = ref<'light' | 'dark'>(
    (storage.getString('theme') as 'light' | 'dark') || 'light'
  )
  const showAuthModal = ref(false)
  const showChangePasswordModal = ref(false)
  const showRenameModal = ref(false)
  const showShareModal = ref(false)
  const renameConvId = ref<string | null>(null)
  const shareConvId = ref<string | null>(null)

  // Apply theme to document
  watch(theme, (val) => {
    document.documentElement.classList.toggle('dark', val === 'dark')
    storage.setString('theme', val)
  }, { immediate: true })

  function toggleSidebar() {
    sidebarOpen.value = !sidebarOpen.value
  }

  function closeSidebarOnMobile() {
    if (window.innerWidth <= 720) {
      sidebarOpen.value = false
    }
  }

  function toggleWebSidebar() {
    webSidebarOpen.value = !webSidebarOpen.value
  }

  function toggleTheme() {
    theme.value = theme.value === 'light' ? 'dark' : 'light'
  }

  function openRenameModal(convId: string) {
    renameConvId.value = convId
    showRenameModal.value = true
  }

  function openShareModal(convId: string) {
    shareConvId.value = convId
    showShareModal.value = true
  }

  return {
    sidebarOpen,
    webSidebarOpen,
    hasWebResults,
    theme,
    showAuthModal,
    showChangePasswordModal,
    showRenameModal,
    showShareModal,
    renameConvId,
    shareConvId,
    toggleSidebar,
    closeSidebarOnMobile,
    toggleWebSidebar,
    toggleTheme,
    openRenameModal,
    openShareModal,
  }
})
