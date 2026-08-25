export type AgentStatus = 'online' | 'offline' | 'idle' | 'unknown'

export interface Agent {
  id: string
  hostname: string
  os: string
  os_version?: string
  username: string
  ip_private?: string
  ip_public?: string
  architecture?: string
  processor?: string
  ram_total?: number
  ram_available?: number
  status: AgentStatus
  last_seen?: string
  created_at?: string
  tags?: string[]
  group_id?: string
  geo_lat?: number
  geo_lng?: number
}
