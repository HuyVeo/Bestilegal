<script setup lang="ts">
import { computed } from 'vue'
import { useConversationsStore } from '@/stores/conversations'
import ConversationItem from './ConversationItem.vue'
import BaseSkeleton from '@/components/ui/BaseSkeleton.vue'
import { groupDateLabel } from '@/lib/format'

const convStore = useConversationsStore()

interface GroupedConversations {
  label: string
  items: typeof convStore.conversations
}

const grouped = computed<GroupedConversations[]>(() => {
  const groups = new Map<string, typeof convStore.conversations>()

  for (const conv of convStore.conversations) {
    const label = groupDateLabel(conv.updated_at)
    if (!groups.has(label)) groups.set(label, [])
    groups.get(label)!.push(conv)
  }

  return Array.from(groups.entries()).map(([label, items]) => ({ label, items }))
})
</script>

<template>
  <!-- Loading skeletons -->
  <div v-if="convStore.loading && !convStore.conversations.length" class="flex flex-col gap-2 px-2">
    <BaseSkeleton v-for="i in 5" :key="i" height="36px" rounded="8px" />
  </div>

  <!-- Grouped list -->
  <div v-else class="flex flex-col gap-1">
    <template v-for="group in grouped" :key="group.label">
      <div class="px-4 pt-3 pb-1">
        <span class="text-[0.65rem] font-bold text-white/30 uppercase tracking-wider">
          {{ group.label }}
        </span>
      </div>
      <ConversationItem
        v-for="conv in group.items"
        :key="conv.id"
        :conversation="conv"
      />
    </template>

    <!-- Empty -->
    <p v-if="!convStore.conversations.length && !convStore.loading" class="text-center text-sm text-white/30 py-8">
      Chưa có cuộc hội thoại nào
    </p>
  </div>
</template>
