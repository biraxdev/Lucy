import api from './client'

export interface DefenseStatus {
  mode: string
  platform: string
  version: string
  stats: {
    events_ingested: number
    alerts_generated: number
    unread_alerts: number
    rules_active: number
    by_severity: Record<string, number>
  }
}

export interface DefenseEvent {
  id: string
  timestamp: string
  source: string
  hostname: string
  event_type: string
  severity: string
  mitre?: string
  details: Record<string, unknown>
}

export interface DefenseAlert {
  id: string
  rule_id: string
  rule_name: string
  severity: string
  mitre?: string
  timestamp: string
  source_event_id: string
  hostname: string
  summary: string
  details: Record<string, unknown>
  read: boolean
}

export interface DefenseRule {
  id: string
  name: string
  description: string
  severity: string
  mitre?: string
  enabled: boolean
}

export interface ScannerInfo {
  id: string
  name: string
  description: string
}

export const getDefenseStatus = () => api.get<DefenseStatus>('/defense/status').then(r => r.data)

export const listDefenseEvents = (params?: { limit?: number; event_type?: string; hostname?: string }) =>
  api.get<DefenseEvent[]>('/defense/events', { params }).then(r => r.data)

export const ingestEvent = (event: Omit<DefenseEvent, 'id' | 'timestamp'>) =>
  api.post<DefenseEvent>('/defense/events', event).then(r => r.data)

export const listDefenseAlerts = (params?: { limit?: number; severity?: string; unread_only?: boolean }) =>
  api.get<DefenseAlert[]>('/defense/alerts', { params }).then(r => r.data)

export const unreadDefenseAlertCount = () =>
  api.get<{ count: number }>('/defense/alerts/unread').then(r => r.data)

export const markDefenseAlertRead = (id: string) =>
  api.post<{ ok: boolean }>(`/defense/alerts/${id}/read`).then(r => r.data)

export const markAllDefenseAlertsRead = () =>
  api.post<{ marked: number }>('/defense/alerts/read-all').then(r => r.data)

export const listDefenseRules = () => api.get<DefenseRule[]>('/defense/rules').then(r => r.data)

export const getMitreMap = () => api.get<{ mapping: Record<string, string[]>; rule_count: number }>('/defense/mitre-map').then(r => r.data)

export const listScanners = () => api.get<ScannerInfo[]>('/defense/scanners').then(r => r.data)

export const runLocalScanner = (scanner: string, action = 'scan', params: Record<string, unknown> = {}) =>
  api.post<Record<string, unknown>>('/defense/scanners/run', { scanner, action, params }).then(r => r.data)

export const dispatchSensorScan = (agent_id: string, scanner: string, action = 'scan', params: Record<string, unknown> = {}, priority = 'normal') =>
  api.post<Record<string, unknown>>('/defense/scanners/dispatch', { agent_id, scanner, action, params, priority }).then(r => r.data)
