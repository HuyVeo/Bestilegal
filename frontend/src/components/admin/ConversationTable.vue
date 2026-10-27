<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { listAllConversations } from '@/api/admin'
import type { Conversation } from '@/types/conversation'
import BaseSpinner from '@/components/ui/BaseSpinner.vue'
import { formatDate, truncate } from '@/lib/format'

const conversations = ref<Conversation[]>([])
const loading = ref(true)
const total = ref(0)

async function load() {
  loading.value = true
  try {
    const data = await listAllConversations()
    conversations.value = data.conversations
    total.value = data.total
  } catch { /* ignore */ }
  loading.value = false
}

onMounted(load)
</script>

<template>
  <div v-if="loading" class="flex justify-center py-12">
    <BaseSpinner />
  </div>

  <div v-else class="overflow-x-auto">
    <table class="w-full text-sm">
      <thead>
        <tr class="border-b border-border-light dark:border-gray-700">
          <th class="text-left py-3 px-4 font-semibold text-text-muted dark:text-gray-400">Tiêu đề</th>
          <th class="text-left py-3 px-4 font-semibold text-text-muted dark:text-gray-400">User</th>
          <th class="text-left py-3 px-4 font-semibold text-text-muted dark:text-gray-400">Messages</th>
          <th class="text-left py-3 px-4 font-semibold text-text-muted dark:text-gray-400">Cập nhật</th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="conv in conversations"
          :key="conv.id"
          class="border-b border-border-light/50 dark:border-gray-700/50 hover:bg-gray-50 dark:hover:bg-gray-800/50"
        >
          <td class="py-3 px-4 text-text-body dark:text-gray-300">{{ truncate(conv.title || 'Untitled', 60) }}</td>
          <td class="py-3 px-4 text-text-muted dark:text-gray-400 text-xs">{{ conv.user_id || 'N/A' }}</td>
          <td class="py-3 px-4 text-text-muted dark:text-gray-400">{{ conv.message_count }}</td>
          <td class="py-3 px-4 text-text-muted dark:text-gray-400">{{ formatDate(conv.updated_at) }}</td>
        </tr>
      </tbody>
    </table>

    <p v-if="!conversations.length" class="text-center text-text-muted dark:text-gray-400 py-8">
      Không có cuộc hội thoại nào
    </p>
  </div>
</template>
