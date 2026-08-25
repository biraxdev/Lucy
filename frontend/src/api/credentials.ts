import api from './client'

export interface Credential {
  id: string
  agent_id: string
  url: string | null
  hostname: string | null
  username: string
  source: string
  confidence: 'high' | 'medium' | 'low'
  score?: number
  tags: string[]
  captured_at: string
  version: number
  seen_count?: number
  last_seen?: string
}

export interface CredentialSearchParams {
  q?: string
  agent_id?: string
  source?: string
  min_score?: number
  limit?: number
  offset?: number
}

export const searchCredentials = (params?: CredentialSearchParams) =>
  api.get<Credential[]>('/credentials', { params }).then(r => r.data)

export const revealCredential = (id: string) =>
  api.get<Credential & { password: string }>(`/credentials/${id}/reveal`).then(r => r.data)

export const deleteCredential = (id: string) =>
  api.delete(`/credentials/${id}`)

export const deleteAllCredentials = () =>
  api.delete('/credentials')

export const exportCredentials = (params?: CredentialSearchParams) =>
  api.get('/credentials/export', { params, responseType: 'blob' }).then(r => r.data)
