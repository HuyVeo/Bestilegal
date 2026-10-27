<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { listUsers, setUserRole, deactivateUser } from '@/api/admin'
import type { AdminUser } from '@/types/admin'
import BaseBadge from '@/components/ui/BaseBadge.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseSpinner from '@/components/ui/BaseSpinner.vue'
import { formatDate } from '@/lib/format'
import { Shield, UserX } from 'lucide-vue-next'

const users = ref<AdminUser[]>([])
const loading = ref(true)
const page = ref(1)
const total = ref(0)

async function loadUsers() {
  loading.value = true
  try {
    const data = await listUsers(page.value)
    users.value = data.users
    total.value = data.total
  } catch { /* ignore */ }
  loading.value = false
}

async function toggleRole(user: AdminUser) {
  const newRole = user.role === 'admin' ? 'user' : 'admin'
  if (!confirm(`Đổi role ${user.email} thành ${newRole}?`)) return
  await setUserRole(user.id, newRole)
  user.role = newRole
}

async function handleDeactivate(user: AdminUser) {
  if (!confirm(`Vô hiệu hóa tài khoản ${user.email}?`)) return
  await deactivateUser(user.id)
  user.is_active = false
}

onMounted(loadUsers)
</script>

<template>
  <div v-if="loading" class="flex justify-center py-12">
    <BaseSpinner />
  </div>

  <div v-else class="overflow-x-auto">
    <table class="w-full text-sm">
      <thead>
        <tr class="border-b border-border-light dark:border-gray-700">
          <th class="text-left py-3 px-4 font-semibold text-text-muted dark:text-gray-400">Email</th>
          <th class="text-left py-3 px-4 font-semibold text-text-muted dark:text-gray-400">Tên</th>
          <th class="text-left py-3 px-4 font-semibold text-text-muted dark:text-gray-400">Role</th>
          <th class="text-left py-3 px-4 font-semibold text-text-muted dark:text-gray-400">Trạng thái</th>
          <th class="text-left py-3 px-4 font-semibold text-text-muted dark:text-gray-400">Ngày tạo</th>
          <th class="text-right py-3 px-4 font-semibold text-text-muted dark:text-gray-400">Thao tác</th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="user in users"
          :key="user.id"
          class="border-b border-border-light/50 dark:border-gray-700/50 hover:bg-gray-50 dark:hover:bg-gray-800/50"
        >
          <td class="py-3 px-4 text-text-body dark:text-gray-300">{{ user.email }}</td>
          <td class="py-3 px-4 text-text-body dark:text-gray-300">{{ user.display_name }}</td>
          <td class="py-3 px-4">
            <BaseBadge :variant="user.role === 'admin' ? 'blue' : 'gray'">
              {{ user.role }}
            </BaseBadge>
          </td>
          <td class="py-3 px-4">
            <BaseBadge :variant="user.is_active ? 'green' : 'red'">
              {{ user.is_active ? 'Active' : 'Inactive' }}
            </BaseBadge>
          </td>
          <td class="py-3 px-4 text-text-muted dark:text-gray-400">{{ formatDate(user.created_at) }}</td>
          <td class="py-3 px-4 text-right">
            <div class="flex items-center justify-end gap-1">
              <BaseButton size="sm" variant="ghost" @click="toggleRole(user)" title="Đổi role">
                <Shield :size="14" />
              </BaseButton>
              <BaseButton size="sm" variant="ghost" @click="handleDeactivate(user)" :disabled="!user.is_active" title="Vô hiệu hóa">
                <UserX :size="14" />
              </BaseButton>
            </div>
          </td>
        </tr>
      </tbody>
    </table>

    <p v-if="!users.length" class="text-center text-text-muted dark:text-gray-400 py-8">Không có user nào</p>
  </div>
</template>
