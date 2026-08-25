export type ChatRole = 'user' | 'assistant' | 'system' | 'event'

export interface ChatMessage {
  id: string
  role: ChatRole
  content: string
  raw_payload?: Record<string, unknown> | null
  source_event_type?: string | null
  channel?: string | null
  agent_id?: string | null
  task_id?: string | null
  metadata?: Record<string, unknown>
  /** Enriched fields from WS broadcast (not persisted) */
  channels?: string[]
  hostname?: string | null
  created_at: string
}

export interface ChatCommandResponse {
  intent: string
  status: string
  message: string
  data: Record<string, unknown>
}

export interface ChatChannel {
  id: string
  label: string
  type: 'global' | 'group'
  color: string
  description?: string
  member_count: number
}
