import api from './client'
import { useAuthStore } from '../stores/authStore'

export interface CopilotContext {
  agents: Array<{ id: string; hostname: string; os: string; status: string; ip: string | null; username: string }>
  recent_tasks: Array<{ id: string; module: string; action: string; status: string; agent_id: string | null }>
  modules: Array<{ id: string; name: string; category: string; description: string }>
  stats: {
    agents: number
    agents_online: number
    tasks: number
    modules: number
    timelines: number
    pocs: number
    credentials: number
    findings: number
  }
}

export interface WebSearchResult {
  query: string
  results: Array<{ title: string; url: string }>
  count: number
  error?: string
}

export interface FetchUrlResult {
  url: string
  content: string
  content_type: string
  length: number
  error?: string
}

export interface DispatchTaskResult {
  task_id: string
  agent_id: string
  module: string
  action: string
  status: string
}

export const getCopilotContext = () =>
  api.get<CopilotContext>('/ai-chat/context').then((r) => r.data)

export const webSearch = (query: string, maxResults = 5) =>
  api.post<WebSearchResult>('/ai-chat/web-search', { query, max_results: maxResults }).then((r) => r.data)

export const fetchUrl = (url: string) =>
  api.post<FetchUrlResult>('/ai-chat/fetch-url', { url }).then((r) => r.data)

export const dispatchTask = (data: { agent_id: string; module: string; action: string; params?: Record<string, unknown>; priority?: string }) =>
  api.post<DispatchTaskResult>('/ai-chat/dispatch-task', data).then((r) => r.data)

export const executePoc = (pocId: string, agentId: string) =>
  api.post('/ai-chat/execute-poc', { poc_id: pocId, agent_id: agentId }).then((r) => r.data)

export interface MissionStepResult {
  type: 'step_start' | 'step_done' | 'step_error'
  step: number
  total: number
  label: string
  status?: string
  insight?: string
  task_id?: string
  result?: unknown
  error?: string
  module?: string
  action?: string
}

export interface MissionSummary {
  type: 'mission_start' | 'mission_done'
  mission_id: string
  title: string
  total_steps?: number
  completed?: number
  failed?: number
  agent_id: string
}

/**
 * Execute a mission with live SSE progress.
 * Yields events as they arrive: mission_start, step_start, step_done, step_error, mission_done.
 */
export async function* executeMission(
  missionId: string,
  agentId: string,
  steps: Array<{ module: string; action: string; params: Record<string, unknown>; label: string; insight: string; timeout?: number }>,
  title: string
): AsyncGenerator<MissionStepResult | MissionSummary> {
  const baseURL = (import.meta as any).env?.VITE_API_URL || ''
  const url = `${baseURL}/api/v1/ai-chat/mission`
  const token = useAuthStore.getState().accessToken

  const resp = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ mission_id: missionId, agent_id: agentId, steps, title }),
  })

  if (!resp.ok || !resp.body) {
    yield { type: 'mission_done', mission_id: missionId, title, agent_id: agentId, completed: 0, failed: steps.length }
    return
  }

  const reader = resp.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    const lines = buffer.split('\n')
    buffer = lines.pop() || ''

    for (const line of lines) {
      const trimmed = line.trim()
      if (!trimmed.startsWith('data: ')) continue
      const data = trimmed.slice(6)
      if (data === '[DONE]') return
      try {
        yield JSON.parse(data)
      } catch {
        // skip malformed
      }
    }
  }
}

/**
 * Stream a chat message via SSE. Returns an async generator of events.
 */
export async function* streamChat(
  message: string,
  sessionId: string,
  contextPage?: string | null,
): AsyncGenerator<{ type: string; content?: string; message?: string }> {
  const baseURL = (import.meta as any).env?.VITE_API_URL || ''
  const url = `${baseURL}/api/v1/ai-chat/stream`
  const token = useAuthStore.getState().accessToken

  const resp = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ message, session_id: sessionId, context_page: contextPage || undefined }),
  })

  if (!resp.ok || !resp.body) {
    yield { type: 'error', message: `HTTP ${resp.status}` }
    return
  }

  const reader = resp.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    const lines = buffer.split('\n')
    buffer = lines.pop() || ''

    for (const line of lines) {
      const trimmed = line.trim()
      if (!trimmed.startsWith('data: ')) continue
      const data = trimmed.slice(6)
      if (data === '[DONE]') return
      try {
        const parsed = JSON.parse(data)
        yield parsed
      } catch {
        // skip malformed
      }
    }
  }
}
