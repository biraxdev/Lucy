import api from './client'

export interface AgentGroup {
  id: string
  name: string
  description: string
  type: 'static' | 'dynamic'
  dynamic_query: string
  members: string[]
  color: string
  tags: string[]
  created_at: string
}

export interface GroupResolve {
  group_id: string
  members: string[]
  count: number
}

export const listGroups = () =>
  api.get<AgentGroup[]>('/groups').then(r => r.data)

export const getGroup = (id: string) =>
  api.get<AgentGroup>(`/groups/${id}`).then(r => r.data)

export const createGroup = (body: {
  name: string
  description?: string
  members?: string[]
  dynamic_query?: string
  color?: string
}) => api.post<AgentGroup>('/groups', body).then(r => r.data)

export const updateGroup = (id: string, body: Partial<{
  name: string
  description: string
  members: string[]
  dynamic_query: string
  color: string
}>) => api.put<AgentGroup>(`/groups/${id}`, body).then(r => r.data)

export const deleteGroup = (id: string) =>
  api.delete(`/groups/${id}`)

export const addMember = (groupId: string, agentId: string) =>
  api.post<AgentGroup>(`/groups/${groupId}/members`, { agent_id: agentId }).then(r => r.data)

export const removeMember = (groupId: string, agentId: string) =>
  api.delete<AgentGroup>(`/groups/${groupId}/members/${agentId}`).then(r => r.data)

export const resolveGroup = (groupId: string) =>
  api.get<GroupResolve>(`/groups/${groupId}/resolve`).then(r => r.data)

export interface GroupSummary {
  group_id: string
  name: string
  color: string
  total: number
  online: number
  idle: number
  offline: number
  os_distribution: Record<string, number>
  last_active: string | null
  is_dynamic?: boolean
}

export const getGroupSummary = (groupId: string) =>
  api.get<GroupSummary>(`/groups/${groupId}/summary`).then(r => r.data)

export const getAllGroupSummaries = () =>
  api.get<GroupSummary[]>('/groups/summaries/all').then(r => r.data)

export const getGroupsForAgent = (agentId: string) =>
  api.get<AgentGroup[]>(`/groups/agent/${agentId}`).then(r => r.data)

export const addMembersBulk = (groupId: string, agentIds: string[]) =>
  api.post<AgentGroup>(`/groups/${groupId}/members/bulk`, { agent_ids: agentIds }).then(r => r.data)

export const removeMembersBulk = (groupId: string, agentIds: string[]) =>
  api.delete<AgentGroup>(`/groups/${groupId}/members/bulk`, { data: { agent_ids: agentIds } }).then(r => r.data)
