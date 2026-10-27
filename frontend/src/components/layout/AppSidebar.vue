<script setup lang="ts">
import { onMounted } from 'vue'
import { useUiStore } from '@/stores/ui'
import { useAuthStore } from '@/stores/auth'
import { useChatStore } from '@/stores/chat'
import { useConversationsStore } from '@/stores/conversations'
import ConversationList from '@/components/conversations/ConversationList.vue'
import NewChatButton from '@/components/conversations/NewChatButton.vue'
import { MessageSquarePlus } from 'lucide-vue-next'

const uiStore = useUiStore()
const authStore = useAuthStore()
const chatStore = useChatStore()
const convStore = useConversationsStore()

onMounted(() => {
  if (authStore.isAuthenticated) {
    convStore.fetchConversations()
  }
})

function handleNewChat() {
  chatStore.startNewChat()
  uiStore.closeSidebarOnMobile()
}
</script>

<template>
  <aside
    :class="[
      'fixed lg:relative z-40 h-full bg-navy flex flex-col transition-all duration-300 ease-in-out',
      uiStore.sidebarOpen
        ? 'w-[290px] min-w-[290px] translate-x-0'
        : 'w-0 min-w-0 -translate-x-full lg:translate-x-0 overflow-hidden'
    ]"
  >
    <!-- Brand -->
    <div class="px-5 pt-5 pb-4 border-b border-white/10 flex-shrink-0">
      <div class="flex items-center gap-2.5">
        <svg class="w-8 h-8 flex-shrink-0" viewBox="0 0 40 40" fill="none">
          <polygon points="20,2 25,14 38,14 28,23 32,36 20,28 8,36 12,23 2,14 15,14"
            fill="none" stroke="#FFD700" stroke-width="2" />
          <polygon points="20,10 23,18 32,18 25,23 28,31 20,26 12,31 15,23 8,18 17,18"
            fill="#FFD700" opacity="0.25" />
        </svg>
        <div>
          <h2 class="font-heading font-extrabold text-white text-[1.3rem] tracking-wide">BASAO</h2>
          <p class="text-[0.72rem] text-white/40 mt-0.5 tracking-wider">AI Legal Assistant</p>
        </div>
      </div>
    </div>

    <!-- New chat button -->
    <div class="px-4 mt-3.5 flex-shrink-0">
      <NewChatButton @click="handleNewChat" />
    </div>

    <!-- Section title -->
    <div class="px-4 pt-4 pb-1.5">
      <span class="text-[0.68rem] font-bold text-white/35 uppercase tracking-[1px]">
        Lịch sử hội thoại
      </span>
    </div>

    <!-- Conversation list -->
    <div class="flex-1 overflow-y-auto px-2 pb-4 scrollbar-thin">
      <ConversationList v-if="authStore.isAuthenticated" />
      <div v-else class="px-4 py-8 text-center">
        <MessageSquarePlus :size="32" class="text-white/20 mx-auto mb-3" />
        <p class="text-sm text-white/40">Đăng nhập để lưu hội thoại</p>
      </div>
    </div>

    <!-- Footer -->
    <div class="px-4 py-3 border-t border-white/8 flex-shrink-0">
      <p class="text-[0.69rem] text-white/35 text-center leading-relaxed">
        AI có thể mắc sai sót. Hãy kiểm tra thông tin quan trọng.
      </p>
    </div>

    <!-- Star watermark -->
    <div class="absolute bottom-[-60px] right-[-60px] w-[220px] h-[220px] pointer-events-none opacity-8">
      <svg viewBox="0 0 100 100" fill="none">
        <polygon points="50,5 61,35 95,35 68,57 79,91 50,70 21,91 32,57 5,35 39,35"
          fill="none" stroke="white" stroke-width="1.5" opacity="0.08" />
      </svg>
    </div>
  </aside>
</template>
