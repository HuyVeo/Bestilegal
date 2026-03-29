<script setup lang="ts">
import { useUiStore } from '@/stores/ui'
import AppHeader from './AppHeader.vue'
import AppSidebar from './AppSidebar.vue'

const uiStore = useUiStore()
</script>

<template>
  <div class="flex h-screen overflow-hidden bg-gray-50 dark:bg-gray-900">
    <!-- Sidebar -->
    <AppSidebar />

    <!-- Mobile overlay -->
    <div
      v-if="uiStore.sidebarOpen"
      class="fixed inset-0 bg-black/30 z-30 lg:hidden"
      @click="uiStore.sidebarOpen = false"
    />

    <!-- Main content -->
    <div class="flex-1 flex flex-col overflow-hidden min-w-0">
      <AppHeader />
      <main class="flex-1 overflow-hidden">
        <slot />
      </main>
    </div>
  </div>
</template>
