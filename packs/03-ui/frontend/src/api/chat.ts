import api from './client'
import { useAuthStore } from '../stores/authStore'
import type { ChatChannel, ChatCommandResponse, ChatMessage } from '../types/chat'

function authHeaders(): Record<string, string> {
  const { accessToken } = useAuthStore.getState()
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`
  try {
    const raw = localStorage.getItem('lucy-tenant')
    if (raw) {
      const parsed = JSON.parse(raw)
      const tenantId = parsed?.state?.activeTenant?.id
      if (tenantId) headers['X-Tenant-ID'] = tenantId
    }
  } catch { /* ignore */ }
  return headers
}

export const sendChatCommand = (message: string, clientContext?: Record<string, unknown>) =>
  api.post<ChatCommandResponse>('/chat/command', { message, client_context: clientContext || {} }).then(r => r.data)

export const getChatHistory = (params?: { channel?: string; limit?: number; offset?: number }) =>
  api.get<ChatMessage[]>('/chat/history', { params }).then(r => r.data)

export const getChatChannels = () =>
  api.get<ChatChannel[]>('/chat/channels').then(r => r.data)

// --- ShannonAi ---

export interface ShannonStatus {
  mode: 'narrative' | 'hybrid' | 'llm'
  event_count: number
  agents_tracked: number
  llm_available: boolean
}

export interface ShannonNarrateResult {
  narrative: string
  log_count?: number
  events?: Array<{
    event_type: string
    agent_id?: string | null
    summary: string
    severity: string
    timestamp: string
  }>
  mode?: string
}

export const getShannonStatus = () =>
  api.get<ShannonStatus>('/chat/shannon/status').then(r => r.data)

export const setShannonMode = (mode: 'narrative' | 'hybrid' | 'llm') =>
  api.post<{ mode: string }>('/chat/shannon/mode', { mode }).then(r => r.data)

export const narrateLogs = (body: { agent_id?: string; limit?: number }) =>
  api.post<ShannonNarrateResult>('/chat/shannon/narrate', body).then(r => r.data)

export const narrateRecent = (limit = 10) =>
  api.get<ShannonNarrateResult>('/chat/shannon/recent', { params: { limit } }).then(r => r.data)

export const narrateAgent = (agentId: string, limit = 8) =>
  api.get<ShannonNarrateResult>(`/chat/shannon/agent/${agentId}`, { params: { limit } }).then(r => r.data)

/**
 * Stream a ShannonAi response via SSE.
 * Calls onChunk for each text chunk and resolves when the stream ends.
 */
export async function streamShannonResponse(
  message: string,
  clientContext?: Record<string, unknown>,
  onChunk?: (chunk: string) => void,
): Promise<string> {
  const base = (api.defaults.baseURL || '/api/v1').replace(/\/$/, '')
  const url = `${base}/chat/shannon/stream`
  const res = await fetch(url, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ message, client_context: clientContext || {} }),
  })
  if (!res.ok || !res.body) throw new Error(`Shannon stream failed: ${res.status}`)

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let full = ''
  let buffer = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''
    for (const line of lines) {
      if (!line.startsWith('data: ')) continue
      try {
        const payload = JSON.parse(line.slice(6))
        if (payload.done) {
          return full
        }
        if (payload.chunk) {
          full += payload.chunk
          onChunk?.(payload.chunk)
        }
      } catch {
        // ignore malformed lines
      }
    }
  }
  return full
}

/**
 * Stream a log-to-dialogue transformation via SSE.
 */
export async function streamShannonLogs(
  body: { agent_id?: string; limit?: number },
  onChunk?: (chunk: string) => void,
): Promise<string> {
  const base = (api.defaults.baseURL || '/api/v1').replace(/\/$/, '')
  const url = `${base}/chat/shannon/stream-logs`
  const res = await fetch(url, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify(body),
  })
  if (!res.ok || !res.body) throw new Error(`Shannon log stream failed: ${res.status}`)

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let full = ''
  let buffer = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''
    for (const line of lines) {
      if (!line.startsWith('data: ')) continue
      try {
        const payload = JSON.parse(line.slice(6))
        if (payload.done) {
          return full
        }
        if (payload.chunk) {
          full += payload.chunk
          onChunk?.(payload.chunk)
        }
      } catch {
        // ignore
      }
    }
  }
  return full
}
