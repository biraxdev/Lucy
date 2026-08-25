export interface Module {
  id: string
  name: string
  version: string
  description: string
  author: string
  dependencies: string[]
  os_compat: string[]
  enabled: boolean
  install_count: number
  signature?: string
  created_at: string
  updated_at?: string
}
