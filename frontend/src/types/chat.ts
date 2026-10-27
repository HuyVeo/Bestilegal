export interface Message {
  role: 'user' | 'assistant'
  content: string
  sources?: Source[]
  timestamp?: string
}

export interface ChatRequest {
  question: string
  messages: Message[]
  conv_id?: string | null
}

export interface Source {
  title: string
  url: string
  snippet?: string
}

export interface LegalArticle {
  document_name: string
  article?: string
  content?: string
  snippet?: string
  score?: number
  from_response?: boolean
  url?: string
}

export interface WebResult {
  title: string
  url: string
  content?: string
  reliability?: number
  publish_date?: string
}

export interface DoneEvent {
  conv_id: string
  final_response: string
  legal_basis: LegalArticle[]
  web_results: WebResult[]
  sources: Source[]
  suggestions: string[]
  warnings: string[]
}

export type SSEEventType = 'chunk' | 'done' | 'error'

export interface SSEEvent {
  type: SSEEventType
  content?: string
  conv_id?: string
  final_response?: string
  legal_basis?: LegalArticle[]
  web_results?: WebResult[]
  sources?: Source[]
  suggestions?: string[]
  warnings?: string[]
}
