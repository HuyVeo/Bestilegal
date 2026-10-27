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
const error = ref('')
const loading = ref(false)

async function handleSubmit() {
  error.value = ''
  loading.value = true
  try {
    await authStore.login(email.value, password.value)
    await convStore.fetchConversations()
    emit('success')
  } catch (e: unknown) {
    error.value = (e as Error).message || 'Đăng nhập thất bại'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <form @submit.prevent="handleSubmit" class="flex flex-col gap-4">
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
      placeholder="Nhập mật khẩu"
    />

    <p v-if="error" class="text-sm text-accent-red font-medium">{{ error }}</p>

    <BaseButton type="submit" :loading="loading" class="w-full mt-1">
      Đăng nhập
    </BaseButton>

    <p class="text-center text-sm text-text-muted dark:text-gray-400">
      Chưa có tài khoản?
      <button type="button" class="text-brand-blue font-semibold hover:underline" @click="emit('switch')">
        Đăng ký
      </button>
    </p>
  </form>
</template>
