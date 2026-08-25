import api from './client'

export interface Tenant {
  id: string
  name: string
  slug: string
  description: string | null
  color: string
  active: boolean
  created_at: string
}

export interface TenantStats {
  tenant_id: string
  agents: number
  tasks: number
  credentials: number
  findings: number
  members: number
}

export const listTenants = () =>
  api.get<Tenant[]>('/tenants').then(r => r.data)

export const createTenant = (data: Partial<Tenant>) =>
  api.post<Tenant>('/tenants', data).then(r => r.data)

export const updateTenant = (id: string, data: Partial<Tenant>) =>
  api.patch<Tenant>(`/tenants/${id}`, data).then(r => r.data)

export const deleteTenant = (id: string) =>
  api.delete(`/tenants/${id}`)

export const getTenantStats = (id: string) =>
  api.get<TenantStats>(`/tenants/${id}/stats`).then(r => r.data)

export const listTenantMembers = (id: string) =>
  api.get<any[]>(`/tenants/${id}/members`).then(r => r.data)

export const assignUser = (tenantId: string, userId: string, role: string) =>
  api.post(`/tenants/${tenantId}/members`, { user_id: userId, role }).then(r => r.data)

export const removeUser = (tenantId: string, userId: string) =>
  api.delete(`/tenants/${tenantId}/members/${userId}`)
