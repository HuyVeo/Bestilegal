import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { storage } from '@/lib/storage'
import * as authApi from '@/api/auth'
import type { User } from '@/types/auth'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(storage.get<User>('user'))
  const accessToken = ref(storage.getString('access_token'))
  const refreshToken = ref(storage.getString('refresh_token'))

  const isAuthenticated = computed(() => !!accessToken.value && !!user.value)
  const isAdmin = computed(() => user.value?.role === 'admin')
  const displayName = computed(() => user.value?.display_name || user.value?.email || '')
  const initials = computed(() => {
    const name = displayName.value
    if (!name) return '?'
    const parts = name.split(' ').filter(Boolean)
    if (parts.length >= 2) return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
    return name.slice(0, 2).toUpperCase()
  })

  function setAuth(data: { access_token: string; refresh_token: string; user: User }) {
    accessToken.value = data.access_token
    refreshToken.value = data.refresh_token
    user.value = data.user
    storage.setString('access_token', data.access_token)
    storage.setString('refresh_token', data.refresh_token)
    storage.set('user', data.user)
  }

  function clearAuth() {
    accessToken.value = ''
    refreshToken.value = ''
    user.value = null
    storage.remove('access_token')
    storage.remove('refresh_token')
    storage.remove('user')
  }

  async function login(email: string, password: string) {
    const data = await authApi.login({ email, password })
    setAuth(data)
  }

  async function register(email: string, password: string, displayName: string) {
    // Backend register doesn't return tokens, so register then login
    await authApi.register({ email, password, display_name: displayName })
    const data = await authApi.login({ email, password })
    setAuth(data)
  }

  async function logout() {
    try {
      await authApi.logout()
    } catch {
      /* ignore */
    }
    clearAuth()
  }

  async function changePassword(oldPassword: string, newPassword: string) {
    await authApi.changePassword({ old_password: oldPassword, new_password: newPassword })
    clearAuth()
  }

  async function fetchMe() {
    try {
      const me = await authApi.getMe()
      user.value = me
      storage.set('user', me)
    } catch {
      clearAuth()
    }
  }

  return {
    user,
    accessToken,
    refreshToken,
    isAuthenticated,
    isAdmin,
    displayName,
    initials,
    login,
    register,
    logout,
    changePassword,
    fetchMe,
    clearAuth,
  }
})
