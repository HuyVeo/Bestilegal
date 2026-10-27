<script setup lang="ts">
import { useAuthStore } from '@/stores/auth'
import BaseAvatar from '@/components/ui/BaseAvatar.vue'
import MarkdownContent from './MarkdownContent.vue'
import MessageActions from './MessageActions.vue'
import LegalBasisSection from '@/components/legal/LegalBasisSection.vue'
import type { Message, LegalArticle } from '@/types/chat'

defineProps<{
  message: Message
  legalBasis?: LegalArticle[]
  isLast?: boolean
}>()

defineEmits<{ retry: [] }>()

const authStore = useAuthStore()
</script>

<template>
  <div
    :class="[
      'flex items-end gap-2.5 px-4 py-1.5 animate-fade-up',
      message.role === 'user' ? 'justify-end' : 'justify-start'
    ]"
  >
    <!-- Bot avatar -->
    <BaseAvatar
      v-if="message.role === 'assistant'"
      initials="BS"
      variant="white"
      size="sm"
    />

    <!-- Bubble -->
    <div
      :class="[
        'max-w-[68%] rounded-2xl px-4 py-3 shadow-sm',
        message.role === 'user'
          ? 'bg-brand-blue text-white rounded-br-md'
          : 'bg-white dark:bg-gray-800 border border-border-light dark:border-gray-700 rounded-bl-md'
      ]"
    >
      <!-- User message: plain text -->
      <p v-if="message.role === 'user'" class="text-sm leading-relaxed whitespace-pre-wrap">
        {{ message.content }}
      </p>

      <!-- Assistant message: markdown -->
      <template v-else>
        <MarkdownContent :content="message.content" />

        <!-- Legal basis -->
        <LegalBasisSection v-if="legalBasis?.length" :articles="legalBasis" class="mt-3" />

        <!-- Actions -->
        <MessageActions class="mt-2" @retry="$emit('retry')" :content="message.content" />
      </template>
    </div>

    <!-- User avatar -->
    <BaseAvatar
      v-if="message.role === 'user'"
      :initials="authStore.initials"
      variant="blue"
      size="sm"
    />
  </div>
</template>
