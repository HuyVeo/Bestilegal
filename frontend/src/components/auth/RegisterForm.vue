<script setup lang="ts">
import { ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useConversationsStore } from '@/stores/conversations'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseInput from '@/components/ui/BaseInput.vue'

const emit = defineEmits<{ success: []; switch: [] }>()
const authStore = useAuthStore()
const convStore = useConversationsStore()

const email = ref('')
const password = ref('')
const displayName = ref('')
const error = ref('')
const loading = ref(false)

async function handleSubmit() {
  error.value = ''

  if (password.value.length < 8) {
    error.value = 'Mật khẩu phải có ít nhất 8 ký tự'
    return
  }

  loading.value = true
  try {
    await authStore.register(email.value, password.value, displayName.value)
    await convStore.fetchConversations()
    emit('success')
  } catch (e: unknown) {
    error.value = (e as Error).message || 'Đăng ký thất bại'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <form @submit.prevent="handleSubmit" class="flex flex-col gap-4">
    <BaseInput
      v-model="displayName"
      label="Tên hiển thị"
      placeholder="Nguyễn Văn A"
    />
    <BaseInput
      v-model="email"
      type="email"
      label="Email"
      placeholder="you@example.com"
    />
    <BaseInput
      v-model="password"
      type="password"
      label="Mật khẩu"
      placeholder="Tối thiểu 8 ký tự"
    />

    <p v-if="error" class="text-sm text-accent-red font-medium">{{ error }}</p>

    <BaseButton type="submit" :loading="loading" class="w-full mt-1">
      Đăng ký
    </BaseButton>

    <p class="text-center text-sm text-text-muted dark:text-gray-400">
      Đã có tài khoản?
      <button type="button" class="text-brand-blue font-semibold hover:underline" @click="emit('switch')">
        Đăng nhập
      </button>
    </p>
  </form>
</template>
