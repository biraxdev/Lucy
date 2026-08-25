import api from './client'

export interface Alert {
  id: string
  event: string
  title: string
  message: string
  severity: 'info' | 'warning' | 'critical'
  agent_id: string | null
  data: Record<string, unknown>
  timestamp: string
  read: boolean
}

export interface Webhook {
  id: string
  name: string
  url: string
  kind: 'slack' | 'discord' | 'generic'
  enabled: boolean
  min_severity: 'info' | 'warning' | 'critical'
  events: string[]
  secret: string
  username?: string
  avatar_url?: string
}

export const listAlerts = (params?: { limit?: number; unread_only?: boolean }) =>
  api.get<Alert[]>('/alerts', { params }).then(r => r.data)

export const getUnreadCount = () =>
  api.get<{ count: number }>('/alerts/unread').then(r => r.data)

export const markRead = (alert_ids?: string[]) =>
  api.post<{ marked: number }>('/alerts/read', { alert_ids }).then(r => r.data)

export const listWebhooks = () =>
  api.get<Webhook[]>('/alerts/webhooks').then(r => r.data)

export const addWebhook = (body: Omit<Webhook, 'id'>) =>
  api.post<Webhook>('/alerts/webhooks', body).then(r => r.data)

export const removeWebhook = (id: string) =>
  api.delete(`/alerts/webhooks/${id}`)

export const testWebhook = (id: string) =>
  api.post<{ ok: boolean; message: string }>(`/alerts/webhooks/${id}/test`).then(r => r.data)
