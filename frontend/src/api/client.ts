import { storage } from '@/lib/storage'

const API_BASE = ''

interface FetchOptions extends RequestInit {
  skipAuth?: boolean
}

async function refreshAccessToken(): Promise<string | null> {
  const refreshToken = storage.getString('refresh_token')
  if (!refreshToken) return null

  try {
    const resp = await fetch(`${API_BASE}/api/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    })

    if (!resp.ok) {
      storage.remove('access_token')
      storage.remove('refresh_token')
      storage.remove('user')
      return null
    }

    const data = await resp.json()
    storage.setString('access_token', data.access_token)
    storage.setString('refresh_token', data.refresh_token)
    return data.access_token
  } catch {
    return null
  }
}

export async function apiFetch<T = unknown>(
  url: string,
  options: FetchOptions = {},
): Promise<T> {
  const { skipAuth, ...fetchOptions } = options

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(fetchOptions.headers as Record<string, string>),
  }

  if (!skipAuth) {
    const token = storage.getString('access_token')
    if (token) {
      headers['Authorization'] = `Bearer ${token}`
    }
  }

  let resp = await fetch(`${API_BASE}${url}`, {
    ...fetchOptions,
    headers,
  })

  // Auto-refresh on 401
  if (resp.status === 401 && !skipAuth) {
    const newToken = await refreshAccessToken()
    if (newToken) {
      headers['Authorization'] = `Bearer ${newToken}`
      resp = await fetch(`${API_BASE}${url}`, {
        ...fetchOptions,
        headers,
      })
    }
  }

  if (!resp.ok) {
    const error = await resp.json().catch(() => ({ error: 'Server error' }))
    throw new Error(error.error || error.message || `HTTP ${resp.status}`)
  }

  return resp.json()
}

export function authHeaders(): Record<string, string> {
  const token = storage.getString('access_token')
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  }
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  return headers
}
