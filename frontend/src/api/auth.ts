import { apiFetch } from './client'
import type { AuthResponse, LoginRequest, RegisterRequest, ChangePasswordRequest, User } from '@/types/auth'

export function login(data: LoginRequest): Promise<AuthResponse> {
  return apiFetch('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify(data),
    skipAuth: true,
  })
}

export function register(data: RegisterRequest): Promise<AuthResponse> {
  return apiFetch('/api/auth/register', {
    method: 'POST',
    body: JSON.stringify(data),
    skipAuth: true,
  })
}

export function logout(revokeAll = false): Promise<void> {
  return apiFetch('/api/auth/logout', {
    method: 'POST',
    body: JSON.stringify({ revoke_all: revokeAll }),
  })
}

export function getMe(): Promise<User> {
  return apiFetch('/api/auth/me')
}

export function updateProfile(displayName: string): Promise<User> {
  return apiFetch('/api/auth/me', {
    method: 'PATCH',
    body: JSON.stringify({ display_name: displayName }),
  })
}

export function changePassword(data: ChangePasswordRequest): Promise<void> {
  return apiFetch('/api/auth/change-password', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}
