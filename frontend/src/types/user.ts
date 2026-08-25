export type UserRole = 'superadmin' | 'admin' | 'operator' | 'viewer'

export interface User {
  id: string
  username: string
  role: UserRole
  email?: string
  tenant_id?: string | null
  created_at: string
  last_login?: string
}

export interface AuthTokens {
  access_token: string
  refresh_token: string
  token_type: string
}
