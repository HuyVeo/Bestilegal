<script setup lang="ts">
import { ref } from 'vue'
import type { Conversation } from '@/types/conversation'
import { useChatStore } from '@/stores/chat'
import { useUiStore } from '@/stores/ui'
import { useConversationsStore } from '@/stores/conversations'
import { getConversation } from '@/api/conversations'
import { MessageSquare, Pencil, Trash2, Share2 } from 'lucide-vue-next'

const props = defineProps<{
  conversation: Conversation
}>()

const chatStore = useChatStore()
const uiStore = useUiStore()
const convStore = useConversationsStore()
const showActions = ref(false)

async function loadConversation() {
  try {
    const data = await getConversation(props.conversation.id)
    chatStore.loadConversation(data.id, data.messages || [])
    uiStore.closeSidebarOnMobile()
  } catch { /* ignore */ }
}

function handleRename() {
  uiStore.openRenameModal(props.conversation.id)
}

function handleShare() {
  uiStore.openShareModal(props.conversation.id)
}

async function handleDelete() {
  if (!confirm('Xóa cuộc hội thoại này?')) return
  await convStore.remove(props.conversation.id)
  if (chatStore.convId === props.conversation.id) {
    chatStore.startNewChat()
  }
}
</script>

<template>
  <div
    :class="[
      'group flex items-center gap-2 px-2.5 py-2 rounded-lg cursor-pointer text-white/70 text-[0.82rem] transition-all duration-150 relative',
      chatStore.convId === conversation.id
        ? 'bg-brand-blue/40 text-white font-semibold'
        : 'hover:bg-white/8'
    ]"
    @click="loadConversation"
    @mouseenter="showActions = true"
    @mouseleave="showActions = false"
  >
    <MessageSquare :size="15" class="flex-shrink-0 opacity-60" />
    <span class="flex-1 truncate">{{ conversation.title || 'Cuộc hội thoại mới' }}</span>

    <!-- Actions -->
    <div
      v-show="showActions"
      class="flex items-center gap-0.5 flex-shrink-0"
      @click.stop
    >
      <button
        class="w-6 h-6 flex items-center justify-center rounded text-white/50 hover:text-white hover:bg-white/12 transition-colors"
        title="Đổi tên"
        @click="handleRename"
      >
        <Pencil :size="12" />
      </button>
      <button
        class="w-6 h-6 flex items-center justify-center rounded text-white/50 hover:text-white hover:bg-white/12 transition-colors"
        title="Chia sẻ"
        @click="handleShare"
      >
        <Share2 :size="12" />
      </button>
      <button
        class="w-6 h-6 flex items-center justify-center rounded text-white/50 hover:text-red-400 hover:bg-white/12 transition-colors"
        title="Xóa"
        @click="handleDelete"
      >
        <Trash2 :size="12" />
      </button>
    </div>
  </div>
</template>
