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
  // ---- Plug-and-play descriptor fields ----
  actions?: string[]
  params_schema?: Record<string, any>
  category?: string
  mitre_techniques?: string[]
  tags?: string[]
  inputs?: string[]
  outputs?: string[]
  expected_duration?: number
}

export interface ModuleDescriptor {
  name: string
  version?: string
  description?: string
  author?: string
  actions: string[]
  params_schema?: Record<string, any>
  category?: string
  mitre_techniques?: string[]
  tags?: string[]
  inputs?: string[]
  outputs?: string[]
  expected_duration?: number
}
