import api from './client'
import type { BuildPack } from '../types/build'

export interface PackForm {
  id: string
  name: string
  description: string
  icon: string
  tags: string[]
  modules: string[]
  build_options: Record<string, any>
}

export interface CombineForm {
  bpid_b: string
  new_id: string
  name: string
}

export const listPacks = (q?: string) =>
  api.get<BuildPack[]>('/build-packs', { params: q ? { q } : undefined }).then(r => r.data)

export const getPack = (bpid: string) =>
  api.get<BuildPack>(`/build-packs/${bpid}`).then(r => r.data)

export const createPack = (data: PackForm) =>
  api.post<BuildPack>('/build-packs', data).then(r => r.data)

export const updatePack = (bpid: string, data: Partial<PackForm>) =>
  api.put<BuildPack>(`/build-packs/${bpid}`, data).then(r => r.data)

export const deletePack = (bpid: string) =>
  api.delete(`/build-packs/${bpid}`)

export const duplicatePack = (bpid: string) =>
  api.post<BuildPack>(`/build-packs/${bpid}/duplicate`).then(r => r.data)

export const combinePack = (bpid: string, data: CombineForm) =>
  api.post<BuildPack>(`/build-packs/${bpid}/combine`, data).then(r => r.data)

export const applyPack = (bpid: string) =>
  api.post<{ bpid: string; name: string; modules: string[]; build_options: Record<string, any> }>(`/build-packs/${bpid}/apply`).then(r => r.data)

export const buildFromPack = (bpid: string) =>
  api.post<{ build_id: string; status: string }>(`/build-packs/${bpid}/build`).then(r => r.data)

export const exportPack = (bpid: string) =>
  api.get<Record<string, any>>(`/build-packs/${bpid}/export`).then(r => r.data)

export const importPack = (data: Record<string, any>) =>
  api.post<BuildPack>('/build-packs/import', data).then(r => r.data)
