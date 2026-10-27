<script setup lang="ts">
import { ref } from 'vue'
import BaseDialog from '@/components/ui/BaseDialog.vue'
import LoginForm from './LoginForm.vue'
import RegisterForm from './RegisterForm.vue'

const emit = defineEmits<{ close: []; success: [] }>()
const activeTab = ref<'login' | 'register'>('login')
</script>

<template>
  <BaseDialog :title="activeTab === 'login' ? 'Đăng nhập' : 'Đăng ký'" @close="emit('close')">
    <!-- Tabs -->
    <div class="flex gap-1 p-1 bg-gray-100 dark:bg-gray-700 rounded-xl mb-5">
      <button
        v-for="tab in (['login', 'register'] as const)"
        :key="tab"
        :class="[
          'flex-1 py-2 text-sm font-semibold rounded-lg transition-all duration-200',
          activeTab === tab
            ? 'bg-white dark:bg-gray-600 text-text-primary dark:text-gray-100 shadow-sm'
            : 'text-text-muted dark:text-gray-400 hover:text-text-body dark:hover:text-gray-300'
        ]"
        @click="activeTab = tab"
      >
        {{ tab === 'login' ? 'Đăng nhập' : 'Đăng ký' }}
      </button>
    </div>

    <LoginForm v-if="activeTab === 'login'" @success="emit('success')" @switch="activeTab = 'register'" />
    <RegisterForm v-else @success="emit('success')" @switch="activeTab = 'login'" />
  </BaseDialog>
</template>
