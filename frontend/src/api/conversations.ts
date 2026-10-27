import { apiFetch } from './client'
import type { Conversation, ConversationListResponse, ShareLink } from '@/types/conversation'

export function listConversations(page = 1, perPage = 30): Promise<Conversation[] | ConversationListResponse> {
  return apiFetch(`/api/conversations?page=${page}&per_page=${perPage}`)
}

export function getConversation(id: string): Promise<Conversation> {
  return apiFetch(`/api/conversations/${id}`)
}

export function renameConversation(id: string, title: string): Promise<Conversation> {
  return apiFetch(`/api/conversations/${id}`, {
    method: 'PATCH',
    body: JSON.stringify({ title }),
  })
}

export function deleteConversation(id: string): Promise<void> {
  return apiFetch(`/api/conversations/${id}`, { method: 'DELETE' })
}

export function shareConversation(id: string, expiresHours?: number): Promise<ShareLink> {
  return apiFetch(`/api/conversations/${id}/share`, {
    method: 'POST',
    body: JSON.stringify({ expires_hours: expiresHours }),
  })
}

export function getSharedConversation(token: string): Promise<Conversation> {
  return apiFetch(`/api/shared/${token}`, { skipAuth: true })
}
