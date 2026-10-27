import type { Message } from './chat'

export interface Conversation {
  id: string
  title: string
  created_at: string
  updated_at: string
  message_count: number
  messages?: Message[]
  user_id?: string
}

export interface ConversationListResponse {
  conversations: Conversation[]
  total: number
  page: number
  per_page: number
  pages: number
}

export interface ShareLink {
  id: string
  share_token: string
  created_at: string
  expires_at?: string
  share_url: string
}
