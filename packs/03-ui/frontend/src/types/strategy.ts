export interface Tactic {
  id: string
  mitre_id: string | null
  name: string
  phase: string | null
  description: string | null
  created_at: string
}

export interface Technique {
  id: string
  mitre_id: string | null
  name: string
  tactic_id: string | null
  description: string | null
  platform: string | null
  data_sources: string[] | null
  created_at: string
}

export interface Campaign {
  id: string
  name: string
  description: string | null
  objective: string | null
  status: string
  start_date: string | null
  end_date: string | null
  metadata: Record<string, unknown> | null
  created_at: string
}

export interface Playbook {
  id: string
  name: string
  description: string | null
  technique_ids: string[] | null
  steps: Array<{
    module: string
    action: string
    params?: Record<string, unknown>
    delay?: number
    priority?: string
  }>
  tags: string[] | null
  created_at: string
}

export interface AgentNote {
  id: string
  agent_id: string | null
  user_id: string | null
  content: string
  category: string
  created_at: string
}
