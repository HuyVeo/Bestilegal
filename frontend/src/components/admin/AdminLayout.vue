<script setup lang="ts">
import { ref } from 'vue'
import { Users, MessageSquare } from 'lucide-vue-next'

const activeTab = ref<'users' | 'conversations'>('users')
</script>

<template>
  <div class="h-full flex flex-col overflow-hidden">
    <!-- Admin header -->
    <div class="flex items-center gap-4 px-6 py-4 border-b border-border-light dark:border-gray-700 flex-shrink-0">
      <h2 class="text-xl font-heading font-bold text-text-primary dark:text-gray-100">Quản trị</h2>
      <div class="flex gap-1 p-1 bg-gray-100 dark:bg-gray-700 rounded-xl">
        <button
          :class="[
            'flex items-center gap-1.5 px-3 py-1.5 text-sm font-semibold rounded-lg transition-all',
            activeTab === 'users'
              ? 'bg-white dark:bg-gray-600 text-text-primary dark:text-gray-100 shadow-sm'
              : 'text-text-muted dark:text-gray-400'
          ]"
          @click="activeTab = 'users'"
        >
          <Users :size="14" />
          Users
        </button>
        <button
          :class="[
            'flex items-center gap-1.5 px-3 py-1.5 text-sm font-semibold rounded-lg transition-all',
            activeTab === 'conversations'
              ? 'bg-white dark:bg-gray-600 text-text-primary dark:text-gray-100 shadow-sm'
              : 'text-text-muted dark:text-gray-400'
          ]"
          @click="activeTab = 'conversations'"
        >
          <MessageSquare :size="14" />
          Conversations
        </button>
      </div>
    </div>

    <!-- Content -->
    <div class="flex-1 overflow-auto p-6">
      <slot :active-tab="activeTab" />
    </div>
  </div>
</template>
