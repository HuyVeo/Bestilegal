<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useUiStore } from '@/stores/ui'
import { useConversationsStore } from '@/stores/conversations'
import BaseDialog from '@/components/ui/BaseDialog.vue'
import BaseInput from '@/components/ui/BaseInput.vue'
import BaseButton from '@/components/ui/BaseButton.vue'

const emit = defineEmits<{ close: [] }>()
const uiStore = useUiStore()
const convStore = useConversationsStore()

const title = ref('')
const loading = ref(false)
const error = ref('')

onMounted(() => {
  const conv = convStore.conversations.find(c => c.id === uiStore.renameConvId)
  if (conv) title.value = conv.title
})

async function handleSubmit() {
  if (!title.value.trim() || !uiStore.renameConvId) return
  loading.value = true
  error.value = ''
  try {
    await convStore.rename(uiStore.renameConvId, title.value.trim())
    emit('close')
  } catch (e: unknown) {
    error.value = (e as Error).message
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <BaseDialog title="Đổi tên hội thoại" @close="emit('close')">
    <form @submit.prevent="handleSubmit" class="flex flex-col gap-4">
      <BaseInput v-model="title" label="Tên mới" placeholder="Nhập tên mới" />
      <p v-if="error" class="text-sm text-accent-red">{{ error }}</p>
      <div class="flex justify-end gap-2">
        <BaseButton variant="secondary" @click="emit('close')">Hủy</BaseButton>
        <BaseButton type="submit" :loading="loading">Lưu</BaseButton>
      </div>
    </form>
  </BaseDialog>
</template>
