<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useUiStore } from '@/stores/ui'
import { useTheme } from '@/composables/useTheme'
import BaseAvatar from '@/components/ui/BaseAvatar.vue'
import { Menu, Sun, Moon, LogOut, Key, Shield, ChevronDown } from 'lucide-vue-next'

const authStore = useAuthStore()
const uiStore = useUiStore()
const { isDark, toggle: toggleTheme } = useTheme()
const router = useRouter()
const showDropdown = ref(false)

function handleLogout() {
  showDropdown.value = false
  authStore.logout()
  uiStore.showAuthModal = true
}

function openChangePassword() {
  showDropdown.value = false
  uiStore.showChangePasswordModal = true
}

function goToAdmin() {
  showDropdown.value = false
  router.push('/admin')
}
</script>

<template>
  <header class="h-[62px] bg-navy flex items-center px-4 gap-3 flex-shrink-0 shadow-lg z-20">
    <!-- Sidebar toggle -->
    <button
      class="w-9 h-9 flex items-center justify-center rounded-lg text-white/70 hover:text-white hover:bg-white/10 transition-colors"
      @click="uiStore.toggleSidebar()"
    >
      <Menu :size="22" />
    </button>

    <!-- Brand -->
    <div class="flex items-center gap-2.5 flex-1">
      <!-- Star SVG -->
      <svg class="w-8 h-8 flex-shrink-0" viewBox="0 0 40 40" fill="none">
        <polygon points="20,2 25,14 38,14 28,23 32,36 20,28 8,36 12,23 2,14 15,14"
          fill="none" stroke="#FFD700" stroke-width="2.5" />
        <polygon points="20,10 23,18 32,18 25,23 28,31 20,26 12,31 15,23 8,18 17,18"
          fill="#FFD700" opacity="0.3" />
      </svg>
      <div>
        <h1 class="font-heading font-extrabold text-white text-lg leading-tight tracking-wide">
          BASAO
        </h1>
        <p class="text-[0.6rem] text-white/40 font-semibold uppercase tracking-[1.2px] font-body">
          AI Assistant
        </p>
      </div>
    </div>

    <!-- Theme toggle -->
    <button
      class="w-9 h-9 flex items-center justify-center rounded-lg text-accent-yellow hover:bg-white/10 transition-colors"
      @click="toggleTheme"
      :title="isDark ? 'Light mode' : 'Dark mode'"
    >
      <Moon v-if="!isDark" :size="18" />
      <Sun v-else :size="18" />
    </button>

    <!-- User menu -->
    <div v-if="authStore.isAuthenticated" class="relative">
      <button
        class="flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-white/10 transition-colors"
        @click="showDropdown = !showDropdown"
      >
        <BaseAvatar :initials="authStore.initials" size="sm" />
        <span class="text-sm text-white/80 font-medium hidden sm:block max-w-[120px] truncate">
          {{ authStore.displayName }}
        </span>
        <ChevronDown :size="14" class="text-white/50" />
      </button>

      <!-- Dropdown -->
      <Transition
        enter-active-class="transition ease-out duration-100"
        enter-from-class="opacity-0 scale-95"
        enter-to-class="opacity-100 scale-100"
        leave-active-class="transition ease-in duration-75"
        leave-from-class="opacity-100 scale-100"
        leave-to-class="opacity-0 scale-95"
      >
        <div
          v-if="showDropdown"
          class="absolute right-0 top-full mt-2 w-52 bg-white dark:bg-gray-800 rounded-xl shadow-xl border border-border-light dark:border-gray-700 overflow-hidden z-50"
          @click.stop
        >
          <div class="px-4 py-3 border-b border-border-light dark:border-gray-700">
            <p class="text-sm font-semibold text-text-primary dark:text-gray-200 truncate">
              {{ authStore.displayName }}
            </p>
            <p class="text-xs text-text-muted dark:text-gray-400 truncate">
              {{ authStore.user?.email }}
            </p>
          </div>
          <div class="py-1">
            <button
              v-if="authStore.isAdmin"
              class="w-full flex items-center gap-2.5 px-4 py-2.5 text-sm text-text-body dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
              @click="goToAdmin"
            >
              <Shield :size="16" class="text-text-muted" />
              Quản trị
            </button>
            <button
              class="w-full flex items-center gap-2.5 px-4 py-2.5 text-sm text-text-body dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
              @click="openChangePassword"
            >
              <Key :size="16" class="text-text-muted" />
              Đổi mật khẩu
            </button>
            <button
              class="w-full flex items-center gap-2.5 px-4 py-2.5 text-sm text-accent-red hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
              @click="handleLogout"
            >
              <LogOut :size="16" />
              Đăng xuất
            </button>
          </div>
        </div>
      </Transition>

      <!-- Click outside -->
      <div
        v-if="showDropdown"
        class="fixed inset-0 z-40"
        @click="showDropdown = false"
      />
    </div>

    <!-- Login button for non-authenticated -->
    <button
      v-else
      class="px-4 py-2 text-sm font-semibold text-white bg-brand-blue rounded-lg hover:bg-brand-blue-light transition-colors"
      @click="uiStore.showAuthModal = true"
    >
      Đăng nhập
    </button>
  </header>
</template>
