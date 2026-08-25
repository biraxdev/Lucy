import api from './client'
import type { Module } from '../types/module'

export const getModules = (params?: Record<string, unknown>) =>
  api.get<Module[]>('/modules', { params }).then(r => r.data)
export const getModule = (id: string) => api.get<Module>(`/modules/${id}`).then(r => r.data)
export const uploadModule = (file: File) => {
  const formData = new FormData()
  formData.append('file', file)
  return api.post<Module>('/modules', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }).then(r => r.data)
}
export const updateModule = (id: string, data: Record<string, unknown>) =>
  api.patch<Module>(`/modules/${id}`, data).then(r => r.data)
export const deleteModule = (id: string) => api.delete(`/modules/${id}`)
export const downloadModule = (name: string) =>
  api.get(`/modules/${name}/download`).then(r => r.data)
