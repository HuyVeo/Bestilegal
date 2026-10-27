<script setup lang="ts">
import { ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useUiStore } from '@/stores/ui'
import BaseDialog from '@/components/ui/BaseDialog.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseInput from '@/components/ui/BaseInput.vue'

const emit = defineEmits<{ close: [] }>()
const authStore = useAuthStore()
const uiStore = useUiStore()

const oldPassword = ref('')
const newPassword = ref('')
const confirmPassword = ref('')
const error = ref('')
const loading = ref(false)

async function handleSubmit() {
  error.value = ''

  if (newPassword.value.length < 8) {
    error.value = 'Mật khẩu mới phải có ít nhất 8 ký tự'
    return
  }
  if (newPassword.value !== confirmPassword.value) {
    error.value = 'Mật khẩu xác nhận không khớp'
    return
  }

  loading.value = true
  try {
    await authStore.changePassword(oldPassword.value, newPassword.value)
    uiStore.showAuthModal = true
    emit('close')
  } catch (e: unknown) {
    error.value = (e as Error).message || 'Đổi mật khẩu thất bại'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <BaseDialog title="Đổi mật khẩu" @close="emit('close')">
    <form @submit.prevent="handleSubmit" class="flex flex-col gap-4">
      <BaseInput v-model="oldPassword" type="password" label="Mật khẩu hiện tại" placeholder="Nhập mật khẩu hiện tại" />
      <BaseInput v-model="newPassword" type="password" label="Mật khẩu mới" placeholder="Tối thiểu 8 ký tự" />
      <BaseInput v-model="confirmPassword" type="password" label="Xác nhận mật khẩu mới" placeholder="Nhập lại mật khẩu mới" />

      <p v-if="error" class="text-sm text-accent-red font-medium">{{ error }}</p>

      <BaseButton type="submit" :loading="loading" class="w-full mt-1">
        Đổi mật khẩu
      </BaseButton>
    </form>
  </BaseDialog>
</template>
