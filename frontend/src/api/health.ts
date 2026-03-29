import { apiFetch } from './client'

export interface HealthResponse {
  status: string
  database: string
  cache: string
  model?: string
}

export interface SuggestionsResponse {
  suggestions: string[]
}

export function getHealth(): Promise<HealthResponse> {
  return apiFetch('/api/health', { skipAuth: true })
}

export function getDefaultSuggestions(): Promise<SuggestionsResponse> {
  return apiFetch('/api/suggestions/default', { skipAuth: true })
}
