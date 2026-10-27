export interface User {
  id: string
  email: string
  display_name: string
  role: 'user' | 'admin'
  created_at: string
}

export interface LoginRequest {
  email: string
  password: string
}

export interface RegisterRequest {
  email: string
  password: string
  display_name: string
}

export interface AuthResponse {
  access_token: string
  refresh_token: string
  user: User
}

export interface ChangePasswordRequest {
  old_password: string
  new_password: string
}
