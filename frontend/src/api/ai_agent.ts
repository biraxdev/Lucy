import api from './client'
import type {
  AIAgentStatus,
  AIAgentResponse,
  AnalyzeThreatRequest,
  GenerateScriptRequest,
  SandboxExecuteRequest,
  SandboxWriteFileRequest,
  RunScriptRequest,
  SuggestStepsRequest,
  AnalyzeResultsRequest,
} from '../types/ai_agent'

export const getAIAgentStatus = () =>
  api.get<AIAgentStatus>('/ai-agent/status').then(r => r.data)

export const analyzeThreat = (data: AnalyzeThreatRequest) =>
  api.post<AIAgentResponse>('/ai-agent/analyze-threat', data).then(r => r.data)

export const generateScript = (data: GenerateScriptRequest) =>
  api.post<AIAgentResponse>('/ai-agent/generate-script', data).then(r => r.data)

export const sandboxExecute = (data: SandboxExecuteRequest) =>
  api.post<AIAgentResponse>('/ai-agent/sandbox/execute', data).then(r => r.data)

export const sandboxWriteFile = (data: SandboxWriteFileRequest) =>
  api.post<AIAgentResponse>('/ai-agent/sandbox/write-file', data).then(r => r.data)

export const sandboxRunScript = (data: RunScriptRequest) =>
  api.post<AIAgentResponse>('/ai-agent/sandbox/run-script', data).then(r => r.data)

export const suggestSteps = (data?: SuggestStepsRequest) =>
  api.post<AIAgentResponse>('/ai-agent/suggest-steps', data || {}).then(r => r.data)

export const analyzeResults = (data: AnalyzeResultsRequest) =>
  api.post<AIAgentResponse>('/ai-agent/analyze-results', data).then(r => r.data)

export const getAIContext = () =>
  api.get<Record<string, unknown>>('/ai-agent/context').then(r => r.data)
