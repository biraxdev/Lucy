import api from './client'

export interface ChatMessageRequest {
  message: string
  session_id?: string
  force_execute?: boolean
}

export interface ChatResponse {
  type: 'chat' | 'clarification' | 'execution_report'
  message: string
  questions?: string[]
  status?: string
  success_count?: number
  error_count?: number
  results?: unknown[]
  [key: string]: unknown
}

export interface ChatHistoryResponse {
  session_id: string
  status: string
  messages: Array<{
    role: string
    content: string
    timestamp: string
    metadata: Record<string, unknown>
  }>
  pending_clarification: unknown
  current_plan: unknown[]
  created_at: string
}

export interface ChatStatusResponse {
  session_id: string
  status: string
  message_count: number
  pending_clarification: boolean
  current_plan_steps: number
}

export const sendChatMessage = (data: ChatMessageRequest) =>
  api.post<ChatResponse>('/ai-chat/message', data).then(r => r.data)

export const getChatHistory = (session_id = 'default') =>
  api.get<ChatHistoryResponse>('/ai-chat/history', { params: { session_id } }).then(r => r.data)

export const clearChat = (session_id = 'default') =>
  api.post('/ai-chat/clear', { session_id }).then(r => r.data)

export const getChatStatus = (session_id = 'default') =>
  api.get<ChatStatusResponse>('/ai-chat/status', { params: { session_id } }).then(r => r.data)
