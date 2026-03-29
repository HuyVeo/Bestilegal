<script setup lang="ts">
import { ref } from 'vue'
import { useUiStore } from '@/stores/ui'
import { shareConversation } from '@/api/conversations'
import BaseDialog from '@/components/ui/BaseDialog.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import { Copy, Check, Link } from 'lucide-vue-next'

const emit = defineEmits<{ close: [] }>()
const uiStore = useUiStore()

const shareUrl = ref('')
const loading = ref(false)
const copied = ref(false)
const error = ref('')

async function createShare() {
  if (!uiStore.shareConvId) return
  loading.value = true
  error.value = ''
  try {
    const data = await shareConversation(uiStore.shareConvId)
    shareUrl.value = data.share_url || `${window.location.origin}/shared/${data.share_token}`
  } catch (e: unknown) {
    error.value = (e as Error).message
  } finally {
    loading.value = false
  }
}

function copyLink() {
  navigator.clipboard.writeText(shareUrl.value).then(() => {
    copied.value = true
    setTimeout(() => { copied.value = false }, 2000)
  })
}

// Auto-create share on mount
createShare()
</script>

<template>
  <BaseDialog title="Chia sẻ hội thoại" @close="emit('close')">
    <div v-if="loading" class="flex items-center justify-center py-6">
      <div class="animate-spin w-6 h-6 border-2 border-brand-blue border-t-transparent rounded-full" />
    </div>

    <div v-else-if="shareUrl" class="flex flex-col gap-4">
      <div class="flex items-center gap-2 p-3 bg-gray-50 dark:bg-gray-700 rounded-xl">
        <Link :size="16" class="text-text-muted flex-shrink-0" />
        <span class="text-sm text-text-body dark:text-gray-300 flex-1 truncate">{{ shareUrl }}</span>
      </div>
      <BaseButton @click="copyLink" class="w-full">
        <Check v-if="copied" :size="16" />
        <Copy v-else :size="16" />
        {{ copied ? 'Đã copy!' : 'Copy link' }}
      </BaseButton>
    </div>

    <p v-if="error" class="text-sm text-accent-red mt-2">{{ error }}</p>
  </BaseDialog>
</template>
