import { apiFetch } from './client'

export interface LegalSearchRequest {
  document_name: string
  article?: string
  rag_content?: string
}

export interface LegalSearchResponse {
  source: string
  content: string
  url?: string
  title?: string
}

export interface LegalCleanRequest {
  content: string
  document_name: string
  article?: string
}

export interface LegalCleanResponse {
  cleaned: string
}

export function searchLegalArticle(data: LegalSearchRequest): Promise<LegalSearchResponse> {
  return apiFetch('/api/legal-article/search', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export function cleanLegalArticle(data: LegalCleanRequest): Promise<LegalCleanResponse> {
  return apiFetch('/api/legal-article/clean', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}
