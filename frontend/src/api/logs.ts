import api from './client'

export interface LogEntry {
  id: string
  agent_id: string | null
  level: 'DEBUG' | 'INFO' | 'WARN' | 'ERROR' | 'CRITICAL'
  module: string
  message: string
  log_type: 'system' | 'agent' | 'task' | 'module' | 'security'
  timestamp: string
}

export interface LogSearchParams {
  agent_id?: string
  level?: string
  log_type?: string
  search?: string
  limit?: number
  offset?: number
}

export const listLogs = (params?: LogSearchParams) =>
  api.get<LogEntry[]>('/logs', { params }).then(r => r.data)

export const clearLogs = () =>
  api.delete<{ deleted: number }>('/logs').then(r => r.data)
