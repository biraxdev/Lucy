import { useEffect, useState, useRef } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import {
  Brain, Terminal, Play, FileCode, AlertTriangle, Lightbulb,
  Activity, Send, Loader2, Check, X, Save, Copy, Wand2,
  Shield, Code, Box, BarChart3, ChevronRight, RefreshCw
} from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  getAIAgentStatus, analyzeThreat, generateScript, sandboxExecute,
  sandboxWriteFile, sandboxRunScript, suggestSteps, analyzeResults, getAIContext
} from '../api/ai_agent'
import { Card } from '../components/ui/Card'
import { PageTransition } from '../components/ui/PageTransition'

interface Message {
  role: 'user' | 'agent' | 'system'
  content: string
  type?: 'text' | 'code' | 'json' | 'error' | 'status'
  timestamp: Date
}

export default function AIAgent() {
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState<Message[]>([])
  const [generatedCode, setGeneratedCode] = useState('')
  const [scriptName, setScriptName] = useState('scanner.py')
  const [activeTab, setActiveTab] = useState<'chat' | 'sandbox' | 'context'>('chat')
  const [sandboxCommand, setSandboxCommand] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)

  const { data: status, isLoading: statusLoading } = useQuery({
    queryKey: ['ai-agent-status'],
    queryFn: getAIAgentStatus,
    refetchInterval: 30000,
  })

  const { data: context, isLoading: contextLoading } = useQuery({
    queryKey: ['ai-agent-context'],
    queryFn: getAIContext,
    enabled: activeTab === 'context',
  })

  const analyzeMut = useMutation({
    mutationFn: analyzeThreat,
    onSuccess: (res) => {
      addMessage('agent', JSON.stringify(res.analysis || res, null, 2), 'json')
    },
    onError: (err: any) => addMessage('agent', err.message, 'error'),
  })

  const generateMut = useMutation({
    mutationFn: generateScript,
    onSuccess: (res) => {
      if (res.code) {
        setGeneratedCode(res.code)
        addMessage('agent', `Script generated successfully. ${res.code.length} chars.`, 'text')
      } else {
        addMessage('agent', JSON.stringify(res, null, 2), 'json')
      }
    },
    onError: (err: any) => addMessage('agent', err.message, 'error'),
  })

  const suggestMut = useMutation({
    mutationFn: suggestSteps,
    onSuccess: (res) => {
      addMessage('agent', JSON.stringify(res.suggestions || res, null, 2), 'json')
    },
    onError: (err: any) => addMessage('agent', err.message, 'error'),
  })

  const sandboxExecMut = useMutation({
    mutationFn: sandboxExecute,
    onSuccess: (res) => {
      addMessage('agent', `Exit code: ${res.returncode}\n\nSTDOUT:\n${res.stdout}\n\nSTDERR:\n${res.stderr}`, 'text')
    },
    onError: (err: any) => addMessage('agent', err.message, 'error'),
  })

  const sandboxWriteMut = useMutation({
    mutationFn: sandboxWriteFile,
    onSuccess: (res) => {
      addMessage('agent', `File written: ${res.status}\n\n${res.stdout || ''}`, 'status')
    },
    onError: (err: any) => addMessage('agent', err.message, 'error'),
  })

  const sandboxRunMut = useMutation({
    mutationFn: sandboxRunScript,
    onSuccess: (res) => {
      addMessage('agent', `Script exit: ${res.returncode}\n\n${res.stdout}\n\n${res.stderr}`, 'text')
    },
    onError: (err: any) => addMessage('agent', err.message, 'error'),
  })

  const analyzeResultsMut = useMutation({
    mutationFn: analyzeResults,
    onSuccess: (res) => {
      addMessage('agent', JSON.stringify(res.analysis || res, null, 2), 'json')
    },
    onError: (err: any) => addMessage('agent', err.message, 'error'),
  })

  function addMessage(role: Message['role'], content: string, type: Message['type'] = 'text') {
    setMessages(prev => [...prev, { role, content, type, timestamp: new Date() }])
  }

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = () => {
    if (!input.trim()) return
    addMessage('user', input)
    const cmd = input.trim().toLowerCase()

    if (cmd.startsWith('/generate') || cmd.startsWith('/gen')) {
      const desc = input.replace(/\/(generate|gen)\s*/i, '')
      generateMut.mutate({ task_description: desc, language: 'python' })
    } else if (cmd.startsWith('/analyze')) {
      const query = input.replace(/\/analyze\s*/i, '')
      analyzeMut.mutate({ query })
    } else if (cmd.startsWith('/suggest')) {
      suggestMut.mutate({})
    } else if (cmd.startsWith('/results')) {
      analyzeResultsMut.mutate({ task_results: [] })
    } else {
      addMessage('agent', 'Available commands: /generate <task>, /analyze <threat>, /suggest, /results', 'text')
    }
    setInput('')
  }

  const isBusy = analyzeMut.isPending || generateMut.isPending || suggestMut.isPending ||
    sandboxExecMut.isPending || sandboxWriteMut.isPending || sandboxRunMut.isPending || analyzeResultsMut.isPending

  return (
    <PageTransition>
      <div className="page-container max-w-6xl space-y-6">
        {/* Header */}
        <div className="flex items-end justify-between">
          <div className="space-y-1">
            <h1 className="text-2xl font-bold flex items-center gap-2">
              <Brain size={24} className="text-success" /> AI Security Architect
            </h1>
            <p className="text-sm text-base-content/50">
              Principal Security Infrastructure Architect — White-box research, automated resilience testing, and defensive tooling.
            </p>
          </div>
          <div className="flex items-center gap-3">
            {statusLoading ? (
              <span className="loading loading-spinner loading-sm text-success" />
            ) : (
              <div className={`badge badge-sm ${status?.available ? 'badge-success' : 'badge-error'} gap-1`}>
                {status?.available ? <Check size={12} /> : <X size={12} />}
                {status?.available ? 'LLM Online' : 'LLM Offline'}
              </div>
            )}
            <div className="badge badge-sm badge-ghost gap-1">
              <Box size={12} />
              {status?.model || 'deepseek-coder-v2:lite'}
            </div>
          </div>
        </div>

        {/* Tabs */}
        <div className="tabs tabs-boxed bg-base-200">
          <button className={`tab gap-1 ${activeTab === 'chat' ? 'tab-active' : ''}`} onClick={() => setActiveTab('chat')}>
            <Terminal size={14} /> Chat
          </button>
          <button className={`tab gap-1 ${activeTab === 'sandbox' ? 'tab-active' : ''}`} onClick={() => setActiveTab('sandbox')}>
            <Box size={14} /> Sandbox
          </button>
          <button className={`tab gap-1 ${activeTab === 'context' ? 'tab-active' : ''}`} onClick={() => setActiveTab('context')}>
            <BarChart3 size={14} /> Context
          </button>
        </div>

        {/* Chat Tab */}
        {activeTab === 'chat' && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            {/* Chat panel */}
            <div className="lg:col-span-2 space-y-4">
              <Card hover={false} className="p-0 h-[500px] flex flex-col">
                <div className="flex-1 overflow-y-auto p-4 space-y-3">
                  {messages.length === 0 && (
                    <div className="text-center text-base-content/30 py-12 space-y-2">
                      <Brain size={32} className="mx-auto opacity-50" />
                      <p className="text-sm">AI Security Architect is ready.</p>
                      <p className="text-xs">Try: /generate HTTP endpoint scanner, /analyze lateral movement, /suggest</p>
                    </div>
                  )}
                  {messages.map((msg, idx) => (
                    <motion.div
                      key={idx}
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                    >
                      <div className={`max-w-[80%] rounded-xl p-3 text-sm ${
                        msg.role === 'user'
                          ? 'bg-success/15 text-success-content'
                          : msg.type === 'error'
                            ? 'bg-error/10 text-error'
                            : 'bg-base-300 text-base-content'
                      }`}>
                        <div className="flex items-center gap-1 mb-1 text-[10px] opacity-50 uppercase">
                          {msg.role === 'user' ? <Terminal size={10} /> : <Brain size={10} />}
                          {msg.role}
                        </div>
                        {msg.type === 'code' ? (
                          <pre className="bg-base-100 rounded p-2 overflow-x-auto font-mono text-xs">{msg.content}</pre>
                        ) : msg.type === 'json' ? (
                          <pre className="bg-base-100 rounded p-2 overflow-x-auto font-mono text-xs">{msg.content}</pre>
                        ) : (
                          <div className="whitespace-pre-wrap">{msg.content}</div>
                        )}
                      </div>
                    </motion.div>
                  ))}
                  {isBusy && (
                    <div className="flex justify-start">
                      <div className="bg-base-300 rounded-xl p-3">
                        <Loader2 size={16} className="animate-spin text-success" />
                      </div>
                    </div>
                  )}
                  <div ref={bottomRef} />
                </div>
                <div className="p-3 border-t border-base-300">
                  <div className="flex gap-2">
                    <input
                      className="input input-sm input-bordered flex-1"
                      placeholder="Type a command or natural language query..."
                      value={input}
                      onChange={(e) => setInput(e.target.value)}
                      onKeyDown={(e) => e.key === 'Enter' && handleSend()}
                      disabled={isBusy}
                    />
                    <button
                      className="btn btn-sm btn-success gap-1"
                      onClick={handleSend}
                      disabled={isBusy || !input.trim()}
                    >
                      <Send size={14} />
                    </button>
                  </div>
                  <div className="flex gap-1 mt-2 flex-wrap">
                    {['/generate HTTP scanner', '/analyze APT29', '/suggest next steps', '/results'].map(cmd => (
                      <button
                        key={cmd}
                        className="badge badge-sm badge-ghost cursor-pointer hover:badge-success"
                        onClick={() => setInput(cmd)}
                      >
                        {cmd}
                      </button>
                    ))}
                  </div>
                </div>
              </Card>
            </div>

            {/* Side panel */}
            <div className="space-y-4">
              <Card hover={false} className="p-4 space-y-3">
                <h3 className="font-semibold text-sm flex items-center gap-2">
                  <Wand2 size={16} className="text-success" /> Quick Actions
                </h3>
                <div className="space-y-2">
                  <button
                    className="btn btn-sm btn-outline w-full gap-1 justify-start"
                    onClick={() => { setInput('/generate modular HTTP endpoint scanner'); handleSend() }}
                    disabled={isBusy}
                  >
                    <Code size={14} /> Generate Scanner
                  </button>
                  <button
                    className="btn btn-sm btn-outline w-full gap-1 justify-start"
                    onClick={() => { setInput('/suggest'); handleSend() }}
                    disabled={isBusy}
                  >
                    <Lightbulb size={14} /> Suggest Steps
                  </button>
                  <button
                    className="btn btn-sm btn-outline w-full gap-1 justify-start"
                    onClick={() => { setInput('/analyze current threat landscape'); handleSend() }}
                    disabled={isBusy}
                  >
                    <AlertTriangle size={14} /> Analyze Threats
                  </button>
                </div>
              </Card>

              <Card hover={false} className="p-4 space-y-3">
                <h3 className="font-semibold text-sm flex items-center gap-2">
                  <FileCode size={16} className="text-success" /> Generated Code
                </h3>
                {generatedCode ? (
                  <div className="space-y-2">
                    <div className="relative">
                      <pre className="bg-base-100 border border-base-300 rounded-lg p-3 overflow-x-auto font-mono text-xs max-h-48">
                        {generatedCode.slice(0, 800)}{generatedCode.length > 800 ? '...' : ''}
                      </pre>
                    </div>
                    <div className="flex gap-2">
                      <button
                        className="btn btn-xs btn-outline gap-1"
                        onClick={() => navigator.clipboard.writeText(generatedCode)}
                      >
                        <Copy size={12} /> Copy
                      </button>
                      <button
                        className="btn btn-xs btn-success gap-1"
                        onClick={() => {
                          sandboxWriteMut.mutate({ path: scriptName, content: generatedCode })
                          addMessage('system', `Saved to sandbox: ${scriptName}`, 'status')
                        }}
                        disabled={sandboxWriteMut.isPending}
                      >
                        <Save size={12} /> Save to Sandbox
                      </button>
                    </div>
                  </div>
                ) : (
                  <p className="text-xs text-base-content/40">No code generated yet.</p>
                )}
              </Card>
            </div>
          </div>
        )}

        {/* Sandbox Tab */}
        {activeTab === 'sandbox' && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <Card hover={false} className="p-4 space-y-4">
              <h3 className="font-semibold text-sm flex items-center gap-2">
                <Terminal size={16} className="text-success" /> Sandbox Terminal
              </h3>
              <div className="space-y-2">
                <label className="text-xs text-base-content/60">Command</label>
                <textarea
                  className="textarea textarea-bordered w-full font-mono text-xs"
                  rows={4}
                  placeholder="e.g., python3 /workspace/scanner.py"
                  value={sandboxCommand}
                  onChange={(e) => setSandboxCommand(e.target.value)}
                />
                <div className="flex gap-2">
                  <button
                    className="btn btn-sm btn-success gap-1"
                    onClick={() => sandboxExecMut.mutate({ command: sandboxCommand, timeout: 120 })}
                    disabled={sandboxExecMut.isPending || !sandboxCommand.trim()}
                  >
                    {sandboxExecMut.isPending ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
                    Execute
                  </button>
                  <button
                    className="btn btn-sm btn-outline gap-1"
                    onClick={() => setSandboxCommand('')}
                  >
                    <X size={14} /> Clear
                  </button>
                </div>
              </div>
            </Card>

            <Card hover={false} className="p-4 space-y-4">
              <h3 className="font-semibold text-sm flex items-center gap-2">
                <Activity size={16} className="text-success" /> Execution Output
              </h3>
              <AnimatePresence>
                {sandboxExecMut.data && (
                  <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="space-y-2"
                  >
                    <div className={`badge badge-sm ${sandboxExecMut.data.returncode === 0 ? 'badge-success' : 'badge-error'}`}>
                      Exit: {sandboxExecMut.data.returncode}
                    </div>
                    <div className="bg-base-100 border border-base-300 rounded-lg p-3 font-mono text-xs overflow-x-auto max-h-64">
                      <div className="text-success mb-1"># STDOUT</div>
                      <pre className="whitespace-pre-wrap">{sandboxExecMut.data.stdout || '(empty)'}</pre>
                      {sandboxExecMut.data.stderr && (
                        <>
                          <div className="text-error mt-2 mb-1"># STDERR</div>
                          <pre className="whitespace-pre-wrap text-error">{sandboxExecMut.data.stderr}</pre>
                        </>
                      )}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </Card>
          </div>
        )}

        {/* Context Tab */}
        {activeTab === 'context' && (
          <div className="space-y-4">
            <Card hover={false} className="p-4">
              <h3 className="font-semibold text-sm flex items-center gap-2 mb-3">
                <BarChart3 size={16} className="text-success" /> Lucy Resource Context
              </h3>
              {contextLoading ? (
                <div className="flex items-center gap-2 text-base-content/50">
                  <Loader2 size={16} className="animate-spin" /> Loading context...
                </div>
              ) : context ? (
                <pre className="bg-base-100 border border-base-300 rounded-lg p-3 overflow-x-auto font-mono text-xs max-h-[500px]">
                  {JSON.stringify(context, null, 2)}
                </pre>
              ) : (
                <p className="text-sm text-base-content/40">No context data available.</p>
              )}
            </Card>
          </div>
        )}
      </div>
    </PageTransition>
  )
}
