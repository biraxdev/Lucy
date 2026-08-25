import axios from 'axios'
import { useAuthStore } from '../stores/authStore'

const api = axios.create({
  baseURL: '/api/v1',
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use((config) => {
  const { accessToken } = useAuthStore.getState()
  if (accessToken) config.headers.Authorization = `Bearer ${accessToken}`
  try {
    const raw = localStorage.getItem('lucy-tenant')
    if (raw) {
      const parsed = JSON.parse(raw)
      const tenantId = parsed?.state?.activeTenant?.id
      if (tenantId) config.headers['X-Tenant-ID'] = tenantId
    }
  } catch { /* ignore */ }
  return config
})

let isRefreshing = false
let refreshPromise: Promise<string> | null = null

async function refreshAccessToken(): Promise<string> {
  const { refreshToken } = useAuthStore.getState()
  if (!refreshToken) throw new Error('No refresh token')
  const { data } = await axios.post('/api/v1/auth/refresh', { refresh_token: refreshToken })
  useAuthStore.getState().setTokens(data.access_token, data.refresh_token ?? refreshToken)
  return data.access_token
}

api.interceptors.response.use(
  (res) => res,
  async (err) => {
    const original = err.config
    if (err.response?.status === 401 && original && !original._retry) {
      original._retry = true
      if (!isRefreshing) {
        isRefreshing = true
        refreshPromise = refreshAccessToken()
          .finally(() => {
            isRefreshing = false
            refreshPromise = null
          })
      }
      try {
        const token = await refreshPromise
        original.headers.Authorization = `Bearer ${token}`
        return api(original)
      } catch {
        useAuthStore.getState().logout()
        window.location.href = '/login'
      }
    }
    return Promise.reject(err)
  }
)

export default api
