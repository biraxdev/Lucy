import api from './client'

export interface ReportRequest {
  type: 'engagement' | 'credentials' | 'technical' | 'findings'
  format: 'html' | 'pdf' | 'json'
  agent_ids?: string[]
  date_range?: { from?: string; to?: string }
}

export interface Report {
  report_id: string
  status: 'queued' | 'building' | 'done' | 'error'
  path?: string
  error?: string
}

export const generateReport = (body: ReportRequest) =>
  api.post<{ report_id: string; status: string }>('/reports', body).then(r => r.data)

export const listReports = () =>
  api.get<Report[]>('/reports').then(r => r.data)

export const getReport = (id: string) =>
  api.get<Report>(`/reports/${id}`).then(r => r.data)

export const downloadReport = async (id: string) => {
  const res = await api.get(`/reports/${id}/download`, { responseType: 'blob' })
  const blob = new Blob([res.data])
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `report_${id}.zip`
  a.click()
  URL.revokeObjectURL(url)
}
