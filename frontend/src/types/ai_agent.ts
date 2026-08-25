export interface AIAgentStatus {
  enabled: boolean
  available: boolean
  model: string
  url: string
  sandbox_container: string
  sandbox_workspace: string
}

export interface AnalyzeThreatRequest {
  query: string
}

export interface GenerateScriptRequest {
  task_description: string
  language?: string
}

export interface SandboxExecuteRequest {
  command: string
  timeout?: number
}

export interface SandboxWriteFileRequest {
  path: string
  content: string
}

export interface RunScriptRequest {
  script_path: string
  args?: string
}

export interface SuggestStepsRequest {
  current_state?: Record<string, unknown>
}

export interface AnalyzeResultsRequest {
  task_results: Record<string, unknown>[]
}

export interface AIAgentResponse {
  status: string
  message?: string
  analysis?: unknown
  suggestions?: unknown
  code?: string
  raw?: string
  returncode?: number
  stdout?: string
  stderr?: string
  command?: string
  structured_logs?: unknown
}
