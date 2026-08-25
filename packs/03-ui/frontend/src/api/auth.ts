import api from './client'
import type { AuthTokens, User } from '../types/user'

export const login = (username: string, password: string) =>
  api.post<AuthTokens>('/auth/login', { username, password }).then(r => r.data)

export const refresh = (refresh_token: string) =>
  api.post<AuthTokens>('/auth/refresh', { refresh_token }).then(r => r.data)

export const me = () => api.get<User>('/auth/me').then(r => r.data)

export const logout = () => api.post('/auth/logout')

export const changePassword = (current_password: string, new_password: string) =>
  api.post('/auth/change-password', { current_password, new_password })

export const changeUsername = (password: string, new_username: string) =>
  api.post('/auth/change-username', { password, new_username })

export const rotateApiKey = () => api.post('/auth/rotate-key')
