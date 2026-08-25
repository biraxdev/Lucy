import { useState, useMemo } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import {
  ChevronLeft, RotateCcw, XCircle, Terminal, Clock, Cpu, Server,
  CheckCircle2, XCircle as FailIcon, Loader2, Circle, Play,
  ArrowRight, Copy, Check, AlertTriangle, Hash, Calendar, Zap, Download, Image as ImageIcon,
  Sparkles,
} from 'lucide-react'
import { useCopilotStore } from '../stores/copilotStore'
import { useTask } from '../hooks/useTasks'
import { useAgent } from '../hooks/useAgents'
import { cancelTask, createTask, updateTask } from '../api/tasks'
import { Card, CardBody, CardMetric } from '../components/ui/Card'
import { StatusBadge } from '../components/ui/StatusBadge'
import { MaaSBreadcrumb, ViewLabel } from '../components/ui/MaaSBreadcrumb'
import { PageTransition } from '../components/ui/PageTransition'
import { useToast } from '../contexts/ToastContext'

const PHASES = [
  { key: 'created',   label: 'Created',   icon: Circle },
  { key: 'queued',    label: 'Queued',    icon: Clock },
  { key: 'running',   label: 'Running',   icon: Loader2 },
  { key: 'completed', label: 'Done',      icon: CheckCircle2 },
] as const

const PHASE_ORDER: Record<string, number> = {
  created: 0, queued: 1, running: 2, completed: 3, failed: 3, cancelled: 3,
}

const PRIORITY_STYLES: Record<string, string> = {
  critical: 'text-rose-400 bg-rose-500/10 border-rose-500/20',
  high:     'text-orange-400 bg-orange-500/10 border-orange-500/20',
  normal:   'text-sky-400 bg-sky-500/10 border-sky-500/20',
  low:      'text-base-content/50 bg-base-300 border-base-content/10',
}

export default function TaskDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const [copied, setCopied] = useState(false)

  const { data: task, isLoading } = useTask(id!)
  const { data: agent } = useAgent(task?.agent_id || '')

  const isRunning = task?.status === 'running' || task?.status === 'queued'

  const cancelMut = useMutation({
    mutationFn: () => cancelTask(id!),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['task', id] })
      qc.invalidateQueries({ queryKey: ['tasks'] })
      toast.addToast({ type: 'info', title: 'Task cancelled' })
    },
    onError: (err: any) => toast.addToast({ type: 'error', title: 'Cancel failed', message: err?.message }),
  })

  const rerunMut = useMutation({
    mutationFn: () => createTask({
      agent_id: task!.agent_id,
      module: task!.module,
      action: task!.action,
      priority: task!.priority as any,
      params: task!.params || {},
    }),
    onSuccess: (newTask: any) => {
      qc.invalidateQueries({ queryKey: ['tasks'] })
      toast.addToast({ type: 'success', title: 'Task re-dispatched' })
      if (newTask?.id) navigate(`/tasks/${newTask.id}`)
    },
    onError: (err: any) => toast.addToast({ type: 'error', title: 'Rerun failed', message: err?.message }),
  })

  const retryMut = useMutation({
    mutationFn: () => updateTask(id!, { status: 'queued' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['task', id] })
      toast.addToast({ type: 'success', title: 'Task re-queued' })
    },
  })

  const currentPhase = task ? PHASE_ORDER[task.status] ?? 0 : 0
  const isFailed = task?.status === 'failed'
  const isCancelled = task?.status === 'cancelled'

  const duration = useMemo(() => {
    if (!task?.executed_at || !task?.created_at) return null
    const ms = new Date(task.executed_at).getTime() - new Date(task.created_at).getTime()
    if (ms < 0) return null
    if (ms < 1000) return `${ms}ms`
    if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`
    return `${(ms / 60_000).toFixed(1)}m`
  }, [task])

  const copyResult = () => {
    if (!task?.result) return
    const text = typeof task.result === 'string' ? task.result : JSON.stringify(task.result, null, 2)
    navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  // Extract base64 image from screenshot/webcam/screen_stream results
  const imageData = useMemo(() => {
    if (!task?.result) return null
    const imageModules = ['screenshot', 'webcam', 'screen_stream']
    if (!imageModules.includes(task.module)) return null
    try {
      const parsed = typeof task.result === 'string' ? JSON.parse(task.result) : task.result
      const data = parsed?.data ?? parsed
      if (!data || typeof data !== 'object') return null
      const b64 = data.image_b64 || data.frame || data.frames?.[0] || data.image
      if (typeof b64 === 'string' && b64.length > 100) return b64
    } catch { /* not JSON */ }
    return null
  }, [task?.result, task?.module])

  const downloadImage = () => {
    if (!imageData) return
    const a = document.createElement('a')
    a.href = `data:image/jpeg;base64,${imageData}`
    a.download = `task_${task?.id?.slice(0, 8)}_${task?.module}.jpg`
    a.click()
  }

  if (isLoading) {
    return (
      <div className="flex justify-center py-20">
        <span className="loading loading-spinner loading-lg text-success" />
      </div>
    )
  }

  if (!task) {
    return (
      <PageTransition>
        <div className="page-container">
          <div className="text-center py-20 space-y-4">
            <AlertTriangle size={40} className="text-base-content/30 mx-auto" />
            <p className="text-base-content/50">Task not found.</p>
            <Link to="/tasks" className="btn btn-sm btn-outline gap-1">
              <ChevronLeft size={14} /> Back to Tasks
            </Link>
          </div>
        </div>
      </PageTransition>
    )
  }

  return (
    <PageTransition>
      <div className="page-container space-y-6">
        {/* Header with MaaS breadcrumb */}
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
          <div className="space-y-2">
            <MaaSBreadcrumb
              macro={{ label: 'Dashboard', to: '/' }}
              micro={{ label: agent?.hostname || 'Agent', to: task.agent_id ? `/agents/${task.agent_id}` : '/agents' }}
              action={{ label: `${task.module} › ${task.action}` }}
            />
            <ViewLabel type="action" label="Task Execution" />
          </div>
          <div className="flex gap-2">
            <button className="btn btn-ghost btn-sm gap-1" onClick={() => navigate(-1)}>
              <ChevronLeft size={14} /> Back
            </button>
            <button
              className="btn btn-sm btn-success gap-1"
              onClick={() => useCopilotStore.getState().openWithMessage(
                `Analyse le résultat de la task ${task.module}/${task.action} (status: ${task.status}) sur l'agent ${agent?.hostname || 'inconnu'}. Dis-moi ce que tu trouves dans le résultat et suggère des prochaines étapes.`
              )}
            >
              <Sparkles size={14} /> Analyser avec l'IA
            </button>
            {isRunning && (
              <motion.button
                whileHover={{ scale: 1.03 }}
                whileTap={{ scale: 0.97 }}
                className="btn btn-sm btn-error gap-1"
                onClick={() => cancelMut.mutate()}
                disabled={cancelMut.isPending}
              >
                <XCircle size={14} /> Cancel
              </motion.button>
            )}
            {isFailed && (
              <motion.button
                whileHover={{ scale: 1.03 }}
                whileTap={{ scale: 0.97 }}
                className="btn btn-sm btn-warning gap-1"
                onClick={() => retryMut.mutate()}
                disabled={retryMut.isPending}
              >
                <RotateCcw size={14} /> Retry
              </motion.button>
            )}
            {!isRunning && (
              <motion.button
                whileHover={{ scale: 1.03 }}
                whileTap={{ scale: 0.97 }}
                className="btn btn-sm btn-success gap-1"
                onClick={() => rerunMut.mutate()}
                disabled={rerunMut.isPending}
              >
                {rerunMut.isPending ? <Loader2 size={14} className="animate-spin" /> : <RotateCcw size={14} />}
                Rerun
              </motion.button>
            )}
          </div>
        </div>

        {/* Task identity card */}
        <Card hover={false} className="p-5">
          <div className="flex flex-col md:flex-row md:items-center gap-6">
            <div className="w-14 h-14 rounded-2xl bg-base-300 flex items-center justify-center shrink-0">
              <Terminal size={24} className="text-success" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-3 mb-1 flex-wrap">
                <h2 className="text-xl font-bold font-mono truncate">{task.module}</h2>
                <ArrowRight size={16} className="text-base-content/40 shrink-0" />
                <h2 className="text-xl font-bold font-mono truncate">{task.action}</h2>
                <StatusBadge status={task.status} />
              </div>
              <p className="text-sm text-base-content/50 font-mono truncate">
                <Hash size={11} className="inline" /> {task.id.slice(0, 8)}…
                {task.timeline_id && <span className="ml-3">timeline: {task.timeline_id.slice(0, 8)}…</span>}
              </p>
            </div>
            <div className="flex gap-2 flex-wrap">
              <span className={`px-3 py-1.5 rounded-lg text-xs font-semibold uppercase tracking-wide border ${PRIORITY_STYLES[task.priority] || PRIORITY_STYLES.normal}`}>
                <Zap size={11} className="inline mr-1" /> {task.priority}
              </span>
              {duration && (
                <span className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-base-300 border border-base-content/10">
                  <Clock size={11} className="inline mr-1" /> {duration}
                </span>
              )}
            </div>
          </div>
        </Card>

        {/* Visual execution timeline */}
        <Card hover={false} className="p-6">
          <h3 className="text-sm font-bold uppercase tracking-wider text-base-content/50 mb-6">
            Execution Timeline
          </h3>
          <div className="flex items-center justify-between relative">
            {/* Progress line background */}
            <div className="absolute top-5 left-0 right-0 h-0.5 bg-base-300 -z-0" />
            {/* Progress line fill */}
            <motion.div
              className="absolute top-5 left-0 h-0.5 bg-success -z-0"
              initial={{ width: 0 }}
              animate={{ width: `${(currentPhase / (PHASES.length - 1)) * 100}%` }}
              transition={{ duration: 0.5, ease: 'easeOut' }}
            />
            {PHASES.map((phase, i) => {
              const reached = i <= currentPhase && !isFailed && !isCancelled
              const isCurrent = i === currentPhase && isRunning
              const Icon = isFailed && i === PHASES.length - 1 ? FailIcon : phase.icon
              return (
                <div key={phase.key} className="flex flex-col items-center gap-2 relative z-10 flex-1">
                  <motion.div
                    initial={{ scale: 0.8, opacity: 0 }}
                    animate={{ scale: 1, opacity: 1 }}
                    transition={{ delay: i * 0.08 }}
                    className={`w-10 h-10 rounded-full flex items-center justify-center border-2 transition-colors ${
                      reached
                        ? 'bg-success border-success text-base-100'
                        : isCurrent
                        ? 'bg-success/20 border-success text-success'
                        : 'bg-base-200 border-base-300 text-base-content/40'
                    } ${isCurrent ? 'animate-pulse' : ''}`}
                  >
                    <Icon
                      size={18}
                      className={isCurrent ? 'animate-spin' : ''}
                    />
                  </motion.div>
                  <span className={`text-xs font-medium ${reached || isCurrent ? 'text-base-content' : 'text-base-content/40'}`}>
                    {phase.label}
                  </span>
                </div>
              )
            })}
          </div>
          {isFailed && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              className="mt-5 flex items-center gap-2 text-rose-400 text-sm"
            >
              <FailIcon size={16} /> Task failed during execution
            </motion.div>
          )}
          {isCancelled && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              className="mt-5 flex items-center gap-2 text-amber-400 text-sm"
            >
              <XCircle size={16} /> Task was cancelled
            </motion.div>
          )}
        </Card>

        {/* Metadata grid + Agent link */}
        <section className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <Card hover={false} className="p-5">
            <h3 className="text-sm font-bold uppercase tracking-wider text-base-content/50 mb-4">Metadata</h3>
            <div className="space-y-3">
              <MetaRow icon={Calendar} label="Created" value={task.created_at ? new Date(task.created_at).toLocaleString() : '—'} />
              <MetaRow icon={Clock} label="Executed" value={task.executed_at ? new Date(task.executed_at).toLocaleString() : '—'} />
              <MetaRow icon={Hash} label="Task ID" value={task.id} mono />
              {task.timeline_id && (
                <MetaRow icon={ArrowRight} label="Timeline" value={task.timeline_id} mono />
              )}
            </div>
          </Card>

          <Card hover={false} className="p-5">
            <h3 className="text-sm font-bold uppercase tracking-wider text-base-content/50 mb-4">Target Agent</h3>
            {agent ? (
              <Link to={`/agents/${agent.id}`} className="block group">
                <div className="flex items-center gap-3 p-3 rounded-xl bg-base-300/50 group-hover:bg-base-300 transition-colors">
                  <div className="w-10 h-10 rounded-xl bg-base-200 flex items-center justify-center text-lg shrink-0">
                    {(agent.os || '').toLowerCase().includes('win') ? '🪟' : (agent.os || '').toLowerCase().includes('darwin') ? '🍎' : '🐧'}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="font-bold text-sm truncate group-hover:text-success transition-colors">{agent.hostname}</p>
                    <p className="text-[10px] text-base-content/50 font-mono truncate">{agent.ip_public || agent.ip_private || 'no ip'}</p>
                  </div>
                  <ArrowRight size={16} className="text-base-content/30 group-hover:text-success group-hover:translate-x-1 transition-all shrink-0" />
                </div>
              </Link>
            ) : (
              <div className="flex items-center gap-3 p-3 rounded-xl bg-base-300/50">
                <Server size={20} className="text-base-content/40" />
                <p className="text-sm text-base-content/50">{task.agent_id || 'No agent assigned'}</p>
              </div>
            )}
          </Card>

          <Card hover={false} className="p-5">
            <h3 className="text-sm font-bold uppercase tracking-wider text-base-content/50 mb-4">Module</h3>
            <div className="flex items-center gap-3 p-3 rounded-xl bg-base-300/50">
              <div className="w-10 h-10 rounded-xl bg-success/10 flex items-center justify-center shrink-0">
                <Cpu size={18} className="text-success" />
              </div>
              <div className="min-w-0">
                <p className="font-bold text-sm font-mono truncate">{task.module}</p>
                <p className="text-[10px] text-base-content/50 font-mono">action: {task.action}</p>
              </div>
            </div>
          </Card>
        </section>

        {/* Params + Result viewer */}
        <section className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {task.params && Object.keys(task.params).length > 0 && (
            <Card hover={false} className="p-5">
              <h3 className="text-sm font-bold uppercase tracking-wider text-base-content/50 mb-3">Parameters</h3>
              <pre className="text-xs font-mono bg-base-300/50 rounded-xl p-4 overflow-x-auto max-h-80 scrollbar-thin">
                {JSON.stringify(task.params, null, 2)}
              </pre>
            </Card>
          )}

          {task.result != null && (
            <Card hover={false} className="p-5">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-bold uppercase tracking-wider text-base-content/50">Result</h3>
                <div className="flex gap-1">
                  {imageData && (
                    <button
                      onClick={downloadImage}
                      className="btn btn-ghost btn-xs gap-1 text-base-content/50 hover:text-success"
                      title="Download image"
                    >
                      <Download size={12} /> Image
                    </button>
                  )}
                  <button
                    onClick={copyResult}
                    className="btn btn-ghost btn-xs gap-1 text-base-content/50 hover:text-success"
                  >
                    {copied ? <Check size={12} className="text-success" /> : <Copy size={12} />}
                    {copied ? 'Copied' : 'Copy'}
                  </button>
                </div>
              </div>
              {/* Image preview for screenshot/webcam/screen_stream results */}
              {imageData && (
                <div className="mb-3 rounded-xl overflow-hidden border border-base-content/10 bg-base-300/30">
                  <div className="flex items-center gap-2 px-3 py-1.5 bg-base-300/50 text-[10px] text-base-content/50 uppercase tracking-wider">
                    <ImageIcon size={11} /> Captured frame
                  </div>
                  <img
                    src={`data:image/jpeg;base64,${imageData}`}
                    alt={`${task.module} result`}
                    className="w-full max-h-96 object-contain"
                  />
                </div>
              )}
              <pre className={`text-xs font-mono rounded-xl p-4 overflow-x-auto max-h-80 scrollbar-thin ${
                isFailed ? 'bg-rose-500/5 text-rose-300' : 'bg-emerald-500/5 text-emerald-300'
              }`}>
                {typeof task.result === 'string' ? task.result : JSON.stringify(task.result, null, 2)}
              </pre>
            </Card>
          )}

          {task.error && (
            <Card hover={false} className="p-5 lg:col-span-2 border-rose-500/20">
              <div className="flex items-center gap-2 mb-3">
                <AlertTriangle size={16} className="text-rose-400" />
                <h3 className="text-sm font-bold uppercase tracking-wider text-rose-400">Error</h3>
              </div>
              <pre className="text-xs font-mono bg-rose-500/5 text-rose-300 rounded-xl p-4 overflow-x-auto max-h-60 scrollbar-thin">
                {task.error}
              </pre>
            </Card>
          )}
        </section>
      </div>
    </PageTransition>
  )
}

function MetaRow({ icon: Icon, label, value, mono }: { icon: React.ElementType; label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex items-center gap-3">
      <Icon size={14} className="text-base-content/40 shrink-0" />
      <div className="min-w-0 flex-1">
        <p className="text-[10px] uppercase tracking-wider text-base-content/40">{label}</p>
        <p className={`text-sm text-base-content/80 truncate ${mono ? 'font-mono' : ''}`}>{value}</p>
      </div>
    </div>
  )
}
