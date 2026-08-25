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

export interface PocTemplate {
  id: string
  puid: string
  name: string
  description: string
  icon: string
  category: string
  trigger: string
  agent_group: string[]
  mitre_techniques?: string[]
  tags?: string[]
  phases?: { label: string; steps: number[] }[]
  steps: TimelineStep[]
  source_file?: string
  created_at: string
  updated_at?: string
}

export interface PocStep extends TimelineStep {
  action_description?: string
}

export interface LiveTaskNode {
  id: string
  order: number
  module: string
  action: string
  params: Record<string, unknown>
  status: TaskStatus
  task_id?: string
  result?: unknown
  error?: string
  started_at?: string
  completed_at?: string
}

