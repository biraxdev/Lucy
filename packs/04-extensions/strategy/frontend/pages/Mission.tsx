import { useState, useEffect, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  Crosshair, Server, ListTodo, Bug, KeyRound, Bell, Activity,
  TrendingUp, AlertTriangle, CheckCircle, XCircle, Clock,
  ArrowRight, Zap, FileText, Target, Radio,
} from 'lucide-react'
import { useAgentStore } from '../stores/agentStore'
import { useUIStore } from '../stores/uiStore'
import { useTaskStore } from '../stores/taskStore'
import { useAgents } from '../hooks/useAgents'
import { useWebSocket } from '../hooks/useWebSocket'
import { useToast } from '../contexts/ToastContext'
import { executeTimeline } from '../api/tasks'
import { getUnreadCount } from '../api/alerts'
import api from '../api/client'
import { Card, CardMetric } from '../components/ui/Card'
import { StatusBadge } from '../components/ui/StatusBadge'
import { MaaSBreadcrumb, ViewLabel } from '../components/ui/MaaSBreadcrumb'
import { PageTransition } from '../components/ui/PageTransition'

const container = { hidden: { opacity: 0 }, show: { opacity: 1, transition: { staggerChildren: 0.05 } } }
const item = { hidden: { opacity: 0, y: 12 }, show: { opacity: 1, y: 0 } }

export default function Mission() {
  const { refetch } = useAgents()
  const agents = useAgentStore((s) => s.agentsArray)
  const openAgent = useUIStore((s) => s.openAgent)
  const tasks = useTaskStore((s) => s.tasksArray)
  const navigate = useNavigate()
  const { on } = useWebSocket()
  const toast = useToast()
  const [predictions, setPredictions] = useState<any[]>([])
  const [credCount, setCredCount] = useState(0)
  const [findingCount, setFindingCount] = useState(0)
  const [unreadAlerts, setUnreadAlerts] = useState(0)

  useEffect(() => {
    api.get<any[]>('/credentials').then(r => setCredCount(r.data.length)).catch(() => {})
    api.get<any[]>('/findings').then(r => setFindingCount(r.data.length)).catch(() => {})
    getUnreadCount().then(r => setUnreadAlerts(r.count)).catch(() => {})
    api.get<any>('/alerts/predictions?active_only=true&limit=10')
      .then(r => setPredictions(r.data?.predictions || []))
      .catch(() => {})
  }, [])

  // Live prediction updates
  useEffect(() => {
    const unsub = on('predictive_alert', () => {
      api.get<any>('/alerts/predictions?active_only=true&limit=10')
        .then(r => setPredictions(r.data?.predictions || []))
        .catch(() => {})
    })
    return unsub
  }, [on])

  const online = useMemo(() => agents.filter((a: any) => a.status === 'online'), [agents])
  const offline = useMemo(() => agents.filter((a: any) => a.status === 'offline'), [agents])
  const recentTasks = useMemo(() => [...tasks].sort((a: any, b: any) =>
    new Date(b.created_at || 0).getTime() - new Date(a.created_at || 0).getTime()
  ).slice(0, 8), [tasks])
  const failedTasks = useMemo(() => tasks.filter((t: any) => t.status === 'failed'), [tasks])
  const runningTasks = useMemo(() => tasks.filter((t: any) => t.status === 'running'), [tasks])

  const handleQuickRecon = async () => {
    try {
      await executeTimeline('recon-default')
      toast.addToast({ type: 'success', title: 'Recon dispatched', message: 'Default recon timeline sent to eligible agents.' })
    } catch {
      toast.addToast({ type: 'error', title: 'Recon failed', message: 'Could not dispatch default recon timeline.' })
    }
  }

  const sevColor = (sev: string) => ({
    critical: 'text-red-400 bg-red-500/10 border-red-500/30',
    warning: 'text-amber-400 bg-amber-500/10 border-amber-500/30',
    info: 'text-sky-400 bg-sky-500/10 border-sky-500/30',
  }[sev] || 'text-base-content/60 bg-base-200 border-base-300')

  return (
    <PageTransition>
      <div className="page-container space-y-6">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
          <div className="space-y-2">
            <MaaSBreadcrumb macro={{ label: 'Mission', to: '/mission' }} />
            <ViewLabel type="macro" label="Unified Mission Control" />
          </div>
          <div className="flex gap-2">
            <button className="btn btn-sm btn-success gap-2" onClick={handleQuickRecon}>
              <Zap size={14} /> Quick Recon
            </button>
            <button className="btn btn-sm btn-outline gap-1" onClick={() => refetch()}>
              <Activity size={14} /> Refresh
            </button>
          </div>
        </div>

        {/* Top metrics row */}
        <motion.div
          variants={container}
          initial="hidden"
          animate="show"
          className="grid grid-cols-2 lg:grid-cols-5 gap-4"
        >
          <motion.div variants={item}>
            <Card hover className="p-4 cursor-pointer" onClick={() => navigate('/agents')}>
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-xl bg-emerald-500/10"><Server size={18} className="text-emerald-400" /></div>
                <div>
                  <p className="text-2xl font-bold">{online.length}</p>
                  <p className="text-[10px] uppercase tracking-wider text-base-content/40">Agents Online</p>
                </div>
              </div>
              <p className="text-[10px] text-base-content/40 mt-2">{offline.length} offline</p>
            </Card>
          </motion.div>

          <motion.div variants={item}>
            <Card hover className="p-4 cursor-pointer" onClick={() => navigate('/tasks')}>
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-xl bg-sky-500/10"><ListTodo size={18} className="text-sky-400" /></div>
                <div>
                  <p className="text-2xl font-bold">{runningTasks.length}</p>
                  <p className="text-[10px] uppercase tracking-wider text-base-content/40">Running Tasks</p>
                </div>
              </div>
              <p className="text-[10px] text-base-content/40 mt-2">{failedTasks.length} failed</p>
            </Card>
          </motion.div>

          <motion.div variants={item}>
            <Card hover className="p-4 cursor-pointer" onClick={() => navigate('/credentials')}>
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-xl bg-rose-500/10"><KeyRound size={18} className="text-rose-400" /></div>
                <div>
                  <p className="text-2xl font-bold">{credCount}</p>
                  <p className="text-[10px] uppercase tracking-wider text-base-content/40">Credentials</p>
                </div>
              </div>
            </Card>
          </motion.div>

          <motion.div variants={item}>
            <Card hover className="p-4 cursor-pointer" onClick={() => navigate('/findings')}>
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-xl bg-orange-500/10"><Bug size={18} className="text-orange-400" /></div>
                <div>
                  <p className="text-2xl font-bold">{findingCount}</p>
                  <p className="text-[10px] uppercase tracking-wider text-base-content/40">Findings</p>
                </div>
              </div>
            </Card>
          </motion.div>

          <motion.div variants={item}>
            <Card hover className="p-4 cursor-pointer" onClick={() => navigate('/alerts')}>
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-xl bg-amber-500/10"><Bell size={18} className="text-amber-400" /></div>
                <div>
                  <p className="text-2xl font-bold">{unreadAlerts}</p>
                  <p className="text-[10px] uppercase tracking-wider text-base-content/40">Unread Alerts</p>
                </div>
              </div>
            </Card>
          </motion.div>
        </motion.div>

        {/* Main grid: agents + tasks */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* Agent fleet */}
          <Card className="p-5" hover={false}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-sm flex items-center gap-2">
                <Server size={14} className="text-success" /> Agent Fleet
              </h3>
              <button className="text-[11px] text-success hover:underline" onClick={() => navigate('/agents')}>
                View all <ArrowRight size={10} className="inline" />
              </button>
            </div>
            <div className="space-y-2 max-h-64 overflow-y-auto scrollbar-thin">
              {agents.length === 0 && <p className="text-center text-base-content/30 py-8 text-sm">No agents deployed yet.</p>}
              {agents.slice(0, 10).map((a: any) => (
                <div
                  key={a.id}
                  onClick={() => openAgent(a.id)}
                  className="flex items-center gap-3 p-2 rounded-lg hover:bg-base-200 cursor-pointer transition-colors"
                >
                  <div className={`w-2 h-2 rounded-full shrink-0 ${a.status === 'online' ? 'bg-emerald-500' : a.status === 'offline' ? 'bg-rose-500' : 'bg-amber-500'}`} />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{a.hostname}</p>
                    <p className="text-[10px] text-base-content/40 truncate font-mono">{a.os} · {a.username}</p>
                  </div>
                  <StatusBadge status={a.status} />
                </div>
              ))}
            </div>
          </Card>

          {/* Recent tasks */}
          <Card className="p-5" hover={false}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-sm flex items-center gap-2">
                <ListTodo size={14} className="text-sky-400" /> Recent Tasks
              </h3>
              <button className="text-[11px] text-success hover:underline" onClick={() => navigate('/tasks')}>
                View all <ArrowRight size={10} className="inline" />
              </button>
            </div>
            <div className="space-y-2 max-h-64 overflow-y-auto scrollbar-thin">
              {recentTasks.length === 0 && <p className="text-center text-base-content/30 py-8 text-sm">No tasks yet.</p>}
              {recentTasks.map((t: any) => (
                <div
                  key={t.id}
                  onClick={() => navigate(`/tasks/${t.id}`)}
                  className="flex items-center gap-3 p-2 rounded-lg hover:bg-base-200 cursor-pointer transition-colors"
                >
                  {t.status === 'completed' ? <CheckCircle size={14} className="text-emerald-400 shrink-0" /> :
                   t.status === 'failed' ? <XCircle size={14} className="text-rose-400 shrink-0" /> :
                   t.status === 'running' ? <Activity size={14} className="text-sky-400 shrink-0 animate-pulse" /> :
                   <Clock size={14} className="text-base-content/40 shrink-0" />}
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{t.module} › {t.action}</p>
                    <p className="text-[10px] text-base-content/40 truncate">{t.agent_id?.slice(0, 8)}</p>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </div>

        {/* Predictive alerts + circular actions */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {/* Predictive intelligence */}
          <Card className="col-span-2 p-5" hover={false}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-sm flex items-center gap-2">
                <TrendingUp size={14} className="text-amber-400" /> Predictive Intelligence
              </h3>
              <span className="badge badge-xs badge-warning gap-1">
                <Radio size={10} /> {predictions.length} active
              </span>
            </div>
            <div className="space-y-3 max-h-48 overflow-y-auto scrollbar-thin">
              {predictions.length === 0 && (
                <div className="text-center text-base-content/30 py-8">
                  <CheckCircle size={24} className="mx-auto mb-2 text-emerald-400/50" />
                  <p className="text-sm">No active threats detected.</p>
                  <p className="text-xs">Predictive engine is monitoring task failures, heartbeat jitter, credential bursts and log anomalies.</p>
                </div>
              )}
              {predictions.map((p: any) => (
                <div key={p.id} className={`flex items-start gap-3 p-3 rounded-lg border ${sevColor(p.severity)}`}>
                  <AlertTriangle size={14} className="shrink-0 mt-0.5" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold truncate">{p.title}</p>
                    <p className="text-xs opacity-80 mt-0.5">{p.message}</p>
                  </div>
                  {p.agent_id && (
                    <button
                      onClick={() => openAgent(p.agent_id)}
                      className="text-[10px] hover:underline shrink-0"
                    >
                      Investigate <ArrowRight size={8} className="inline" />
                    </button>
                  )}
                </div>
              ))}
            </div>
          </Card>

          {/* Circular quick actions */}
          <Card className="p-5" hover={false}>
            <h3 className="font-semibold text-sm flex items-center gap-2 mb-4">
              <Crosshair size={14} className="text-success" /> Circular Actions
            </h3>
            <div className="space-y-2">
              <ActionRow icon={Zap} label="Quick Recon" desc="Dispatch recon to all online" onClick={handleQuickRecon} color="text-success" />
              <ActionRow icon={FileText} label="Generate Report" desc="Create engagement report" onClick={() => navigate('/reports')} color="text-sky-400" />
              <ActionRow icon={Target} label="Run Timeline" desc="Execute a planned scenario" onClick={() => navigate('/timelines')} color="text-amber-400" />
              <ActionRow icon={Bug} label="New Finding" desc="Log a security finding" onClick={() => navigate('/findings')} color="text-orange-400" />
              <ActionRow icon={Server} label="Build Agent" desc="Create new payload" onClick={() => navigate('/builder')} color="text-rose-400" />
            </div>
          </Card>
        </div>
      </div>
    </PageTransition>
  )
}

function ActionRow({ icon: Icon, label, desc, onClick, color }: {
  icon: React.ElementType; label: string; desc: string; onClick: () => void; color: string
}) {
  return (
    <motion.button
      whileHover={{ x: 2 }}
      onClick={onClick}
      className="w-full flex items-center gap-3 p-2.5 rounded-lg hover:bg-base-200 transition-colors text-left"
    >
      <Icon size={16} className={`${color} shrink-0`} />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium">{label}</p>
        <p className="text-[10px] text-base-content/40">{desc}</p>
      </div>
      <ArrowRight size={12} className="text-base-content/30 shrink-0" />
    </motion.button>
  )
}
