export type TaskStatus = 'queued' | 'running' | 'completed' | 'failed' | 'cancelled'
export type TaskPriority = 'critical' | 'high' | 'normal' | 'low'

export interface Task {
  id: string
  agent_id: string
  module: string
  action: string
  params?: Record<string, unknown>
  status: TaskStatus
  priority: TaskPriority
  result?: unknown
  error?: string
  created_at: string
  executed_at?: string
  timeline_id?: string
}

export interface TimelineStep {
  order: number
  module: string
  action: string
  params: Record<string, unknown>
  delay: number
  timeout: number
  priority: TaskPriority
}

export interface Timeline {
  id: string
  name: string
  description: string
  agent_group: string[]
  steps: TimelineStep[]
  trigger: string
  loop: number | boolean
  status: 'draft' | 'active' | 'completed' | 'failed'
  created_at: string
}
