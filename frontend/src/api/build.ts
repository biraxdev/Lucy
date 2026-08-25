import api from './client'
import type { BuildPack } from '../types/build'

export const getBuildPacks = () => api.get<BuildPack[]>('/build-packs').then(r => r.data)
export const getBuildPack = (bpid: string) => api.get<BuildPack>(`/build-packs/${bpid}`).then(r => r.data)

export interface BuildPackCreate {
  id: string
  name: string
  description?: string
  icon?: string
  tags?: string[]
  modules?: string[]
  build_options?: Record<string, any>
}

export const createBuildPack = (data: BuildPackCreate) =>
  api.post<BuildPack>('/build-packs', data).then(r => r.data)
