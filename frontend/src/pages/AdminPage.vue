<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import AdminLayout from '@/components/admin/AdminLayout.vue'
import UserTable from '@/components/admin/UserTable.vue'
import ConversationTable from '@/components/admin/ConversationTable.vue'

const authStore = useAuthStore()
const router = useRouter()

onMounted(() => {
  if (!authStore.isAdmin) {
    router.push('/')
  }
})
</script>

<template>
  <AdminLayout v-if="authStore.isAdmin" v-slot="{ activeTab }">
    <UserTable v-if="activeTab === 'users'" />
    <ConversationTable v-else />
  </AdminLayout>
</template>
