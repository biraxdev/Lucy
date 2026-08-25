export interface BuildPack {
  id: string
  bpid: string
  name: string
  description: string
  icon: string
  tags?: string[]
  modules: string[]
  build_options: Record<string, any>
  source_file?: string
  created_at: string
  updated_at?: string
}
