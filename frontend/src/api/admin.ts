import { apiFetch } from './client'
import type { AdminUserListResponse } from '@/types/admin'
import type { ConversationListResponse } from '@/types/conversation'

export function listUsers(page = 1, perPage = 20): Promise<AdminUserListResponse> {
  return apiFetch(`/api/admin/users?page=${page}&per_page=${perPage}`)
}

export function setUserRole(userId: string, role: 'user' | 'admin'): Promise<void> {
  return apiFetch(`/api/admin/users/${userId}/role`, {
    method: 'PATCH',
    body: JSON.stringify({ role }),
  })
}

export function deactivateUser(userId: string): Promise<void> {
  return apiFetch(`/api/admin/users/${userId}`, { method: 'DELETE' })
}

export function listAllConversations(page = 1, perPage = 20): Promise<ConversationListResponse> {
  return apiFetch(`/api/admin/conversations?page=${page}&per_page=${perPage}`)
}
