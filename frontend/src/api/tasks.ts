import api from './client'
import type { Task, Timeline, PocTemplate } from '../types/task'

export const getTasks = (params?: Record<string, unknown>) =>
  api.get<Task[]>('/tasks', { params }).then(r => r.data)
export const getTask = (id: string) => api.get<Task>(`/tasks/${id}`).then(r => r.data)
export const createTask = (data: Partial<Task>) =>
  api.post<Task>('/tasks', data).then(r => r.data)
export const updateTask = (id: string, data: Partial<Task>) =>
  api.patch<Task>(`/tasks/${id}`, data).then(r => r.data)
export const cancelTask = (id: string) => api.delete(`/tasks/${id}`)

export const getTimelines = () => api.get<Timeline[]>('/timelines').then(r => r.data)
export const getTimeline = (id: string) => api.get<Timeline>(`/timelines/${id}`).then(r => r.data)
export const createTimeline = (data: Partial<Timeline>) =>
  api.post<Timeline>('/timelines', data).then(r => r.data)
export const updateTimeline = (id: string, data: Partial<Timeline>) =>
  api.put<Timeline>(`/timelines/${id}`, data).then(r => r.data)
export const executeTimeline = (id: string, agent_ids?: string[]) =>
  api.post(`/timelines/${id}/execute`, { agent_ids }).then(r => r.data)
export const deleteTimeline = (id: string) => api.delete(`/timelines/${id}`)
export const getTimelineTasks = (id: string) => api.get<Task[]>(`/timelines/${id}/tasks`).then(r => r.data)

export const getTemplates = () => api.get<PocTemplate[]>('/timelines/templates').then(r => r.data)
export const importTemplate = (templateId: string) =>
  api.post<Timeline>(`/timelines/templates/${templateId}/import`).then(r => r.data)

export const getPocs = () => api.get<PocTemplate[]>('/pocs').then(r => r.data)
export const getPoc = (id: string) => api.get<PocTemplate>(`/pocs/${id}`).then(r => r.data)
export const importPoc = (id: string) => api.post<Timeline>(`/pocs/${id}/import`).then(r => r.data)
