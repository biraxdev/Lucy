import api from './client'
import type { AgentNote, Campaign, Playbook, Tactic, Technique } from '../types/strategy'

// Tactics
export const getTactics = () => api.get<Tactic[]>('/strategy/tactics').then(r => r.data)
export const createTactic = (data: Partial<Tactic>) =>
  api.post<Tactic>('/strategy/tactics', data).then(r => r.data)

// Techniques
export const getTechniques = (tactic_id?: string) =>
  api.get<Technique[]>('/strategy/techniques', { params: { tactic_id } }).then(r => r.data)
export const createTechnique = (data: Partial<Technique>) =>
  api.post<Technique>('/strategy/techniques', data).then(r => r.data)

// Campaigns
export const getCampaigns = (status?: string) =>
  api.get<Campaign[]>('/strategy/campaigns', { params: { status } }).then(r => r.data)
export const createCampaign = (data: Partial<Campaign>) =>
  api.post<Campaign>('/strategy/campaigns', data).then(r => r.data)
export const updateCampaign = (id: string, data: Partial<Campaign>) =>
  api.put<Campaign>(`/strategy/campaigns/${id}`, data).then(r => r.data)

// Playbooks
export const getPlaybooks = () => api.get<Playbook[]>('/strategy/playbooks').then(r => r.data)
export const createPlaybook = (data: Partial<Playbook>) =>
  api.post<Playbook>('/strategy/playbooks', data).then(r => r.data)

// Agent notes
export const getAgentNotes = (agent_id?: string, category?: string) =>
  api.get<AgentNote[]>('/strategy/notes', { params: { agent_id, category } }).then(r => r.data)
export const createAgentNote = (data: { agent_id: string; content: string; category?: string }) =>
  api.post<AgentNote>('/strategy/notes', data).then(r => r.data)
export const deleteAgentNote = (id: string) => api.delete(`/strategy/notes/${id}`)
