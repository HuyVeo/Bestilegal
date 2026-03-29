<script setup lang="ts">
import { onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useUiStore } from '@/stores/ui'
import { useConversationsStore } from '@/stores/conversations'
import AppLayout from '@/components/layout/AppLayout.vue'
import AuthModal from '@/components/auth/AuthModal.vue'
import ChangePasswordDialog from '@/components/auth/ChangePasswordDialog.vue'
import RenameDialog from '@/components/conversations/RenameDialog.vue'
import ShareDialog from '@/components/conversations/ShareDialog.vue'

const authStore = useAuthStore()
const uiStore = useUiStore()
const convStore = useConversationsStore()
const route = useRoute()

onMounted(async () => {
  if (authStore.accessToken) {
    await authStore.fetchMe()
  }
  if (!authStore.isAuthenticated && route.name !== 'shared') {
    uiStore.showAuthModal = true
  }
})

function handleAuthClose() {
  // Only allow closing if authenticated
  if (authStore.isAuthenticated) {
    uiStore.showAuthModal = false
  }
}

async function handleAuthSuccess() {
  uiStore.showAuthModal = false
  // Reload conversations after login/register
  await convStore.fetchConversations()
}

// Watch for auth state changes - show modal if logged out
watch(() => authStore.isAuthenticated, (isAuth) => {
  if (!isAuth && route.name !== 'shared') {
    uiStore.showAuthModal = true
  }
})
</script>

<template>
  <AppLayout>
    <router-view />
  </AppLayout>

  <AuthModal
    v-if="uiStore.showAuthModal"
    @close="handleAuthClose"
    @success="handleAuthSuccess"
  />
  <ChangePasswordDialog
    v-if="uiStore.showChangePasswordModal"
    @close="uiStore.showChangePasswordModal = false"
  />
  <RenameDialog
    v-if="uiStore.showRenameModal"
    @close="uiStore.showRenameModal = false"
  />
  <ShareDialog
    v-if="uiStore.showShareModal"
    @close="uiStore.showShareModal = false"
  />
</template>
