import api from './client'
import type { Agent } from '../types/agent'

export const getAgents = () => api.get<Agent[]>('/agents').then(r => r.data)
export const getAgent = (id: string) => api.get<Agent>(`/agents/${id}`).then(r => r.data)
export const updateAgent = (id: string, data: Partial<Agent>) =>
  api.patch<Agent>(`/agents/${id}`, data).then(r => r.data)
export const deleteAgent = (id: string) => api.delete(`/agents/${id}`)
export const registerAgent = (data: Record<string, unknown>) =>
  api.post('/agents/register', data).then(r => r.data)
export const killAgent = (id: string) =>
  api.post(`/agents/${id}/kill`).then(r => r.data)
