export interface AdminUser {
  id: string
  email: string
  display_name: string
  role: 'user' | 'admin'
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface AdminUserListResponse {
  users: AdminUser[]
  total: number
  page: number
  per_page: number
}
