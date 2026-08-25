import { useState, useEffect, useMemo, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  LineChart, Line, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, Tooltip, ResponsiveContainer, Legend,
} from 'recharts'
import {
  Server, ListTodo, KeyRound, RefreshCw, Terminal, Zap, Bell, Bug, FileText,
  Radio, ShieldAlert, Activity, Plus, Crosshair,
} from 'lucide-react'
import { useAgentStore } from '../stores/agentStore'
import { useUIStore } from '../stores/uiStore'
import { useTaskStore } from '../stores/taskStore'
import { useAgents } from '../hooks/useAgents'
import { useWebSocket } from '../hooks/useWebSocket'
import { useToast } from '../contexts/ToastContext'
import { executeTimeline } from '../api/tasks'
import { getUnreadCount } from '../api/alerts'
import type { Agent } from '../types/agent'
import api from '../api/client'
import { Card, CardMetric } from '../components/ui/Card'
import { AgentCard } from '../components/ui/AgentCard'
import { QuickAction } from '../components/ui/QuickAction'
import { StatusBadge } from '../components/ui/StatusBadge'
import { MaaSBreadcrumb, ViewLabel } from '../components/ui/MaaSBreadcrumb'
import { PageTransition } from '../components/ui/PageTransition'
import { translateEvent } from '../lib/feedTranslator'
import type { FeedItem as TranslatedFeedItem } from '../lib/feedTranslator'
import { HeatmapCard } from '../components/ui/HeatmapCard'
import AgentMetricsWidget from '../components/ui/AgentMetricsWidget'
import ServerMetricsWidget from '../components/ui/ServerMetricsWidget'

const PIE_COLORS = ['#22c55e', '#f59e0b', '#ef4444', '#6366f1']
const OS_COLORS: Record<string, string> = { windows: '#3b82f6', linux: '#22c55e', darwin: '#f59e0b' }

interface FeedItem { id: string; type: string; message: string; ts: string; icon: React.ElementType; color: string; agentName?: string }
type FeedItemTyped = TranslatedFeedItem

const container = { hidden: { opacity: 0 }, show: { opacity: 1, transition: { staggerChildren: 0.04 } } }
const item = { hidden: { opacity: 0, y: 12 }, show: { opacity: 1, y: 0 } }

export default function Dashboard() {
  const { refetch } = useAgents()
  const agents = useAgentStore((s) => s.agentsArray)
  const openAgent = useUIStore((s) => s.openAgent)
  const tasks = useTaskStore((s) => s.tasksArray)
  const navigate = useNavigate()
  const { on } = useWebSocket()
  const agentsRef = useRef(agents)
  agentsRef.current = agents
  const [feed, setFeed] = useState<FeedItem[]>([])
  const [agentFilter, setAgentFilter] = useState<'all' | 'online' | 'offline' | 'idle'>('all')

  // --- Live polling queries (AJAX auto-refresh) ---
  const { data: credCount = 0 } = useQuery({
    queryKey: ['dashboard-credentials'],
    queryFn: () => api.get<any[]>('/credentials').then(r => r.data.length).catch(() => 0),
    refetchInterval: 15_000,
  })
  const { data: findingCount = 0 } = useQuery({
    queryKey: ['dashboard-findings'],
    queryFn: () => api.get<any[]>('/findings').then(r => r.data.length).catch(() => 0),
    refetchInterval: 15_000,
  })
  const { data: unreadAlertsData } = useQuery({
    queryKey: ['dashboard-unread-alerts'],
    queryFn: () => getUnreadCount().catch(() => ({ count: 0 })),
    refetchInterval: 10_000,
  })
  const unreadAlerts = unreadAlertsData?.count ?? 0

  const online = useMemo(() => agents.filter((a) => a.status === 'online').length, [agents])
  const offline = useMemo(() => agents.filter((a) => a.status === 'offline').length, [agents])
  const idle = useMemo(() => agents.filter((a) => a.status === 'idle').length, [agents])
  const queued = useMemo(() => tasks.filter((t) => t.status === 'queued').length, [tasks])
  const completed = useMemo(() => tasks.filter((t) => t.status === 'completed').length, [tasks])
  const failed = useMemo(() => tasks.filter((t) => t.status === 'failed').length, [tasks])
  const running = useMemo(() => tasks.filter((t) => t.status === 'running').length, [tasks])

  const filteredAgents = useMemo(() => {
    if (agentFilter === 'all') return agents
    return agents.filter((a) => a.status === agentFilter)
  }, [agents, agentFilter])

  const osDist = useMemo(() => Object.entries(
    agents.reduce<Record<string, number>>((acc, a) => {
      const raw = (a.os || 'unknown').toLowerCase()
      const os = raw.includes('win') ? 'windows' : raw.includes('darwin') ? 'darwin' : 'linux'
      acc[os] = (acc[os] || 0) + 1
      return acc
    }, {})
  ).map(([name, value]) => ({ name, value })), [agents])

  const moduleBarData = useMemo(() => {
    const taskByModule = tasks.reduce<Record<string, number>>((acc, t) => {
      acc[t.module || 'unknown'] = (acc[t.module || 'unknown'] || 0) + 1
      return acc
    }, {})
    return Object.entries(taskByModule)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5)
      .map(([name, count]) => ({ name, count }))
  }, [tasks])

  const { data: connHistory } = useQuery({
    queryKey: ['agent-history'],
    queryFn: () => api.get<any>('/monitor/agent-history').then(r => r.data).catch(() => null),
    refetchInterval: 60_000,
  })

  const connLine = useMemo(() => {
    if (Array.isArray(connHistory?.hourly) && connHistory.hourly.length > 0) {
      return connHistory.hourly
    }
    const now = Date.now()
    return Array.from({ length: 24 }, (_, i) => {
      const h = new Date(now - (23 - i) * 3600_000)
      return { time: `${h.getHours()}:00`, online: 0 }
    })
  }, [connHistory])

  useEffect(() => {
    const unsub = on('*', (msg) => {
      const translated = translateEvent(msg as any, agentsRef.current)
      if (!translated) return
      setFeed((prev) => [translated, ...prev.slice(0, 49)])
    })
    return unsub
  }, [on])

  const toast = useToast()

  const handleQuickRecon = async () => {
    try {
      await executeTimeline('recon-default')
      toast.addToast({ type: 'success', title: 'Recon dispatched', message: 'Default recon timeline sent to eligible agents.' })
    } catch {
      toast.addToast({ type: 'error', title: 'Recon failed', message: 'Could not dispatch default recon timeline.' })
    }
  }

  return (
    <PageTransition>
      <div className="page-container space-y-8">
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
          <div className="space-y-2">
            <MaaSBreadcrumb macro={{ label: 'Dashboard', to: '/' }} />
            <ViewLabel type="macro" label="Mission Control" />
          </div>
          <div className="flex gap-2">
            {unreadAlerts > 0 && (
              <motion.button
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                onClick={() => navigate('/alerts')}
                className="btn btn-sm btn-warning gap-2"
              >
                <ShieldAlert size={14} /> {unreadAlerts} alert{unreadAlerts > 1 ? 's' : ''}
              </motion.button>
            )}
            <button className="btn btn-sm btn-success gap-2" onClick={() => navigate('/mission')}>
              <Crosshair size={14} /> Mission View
            </button>
            <button className="btn btn-sm btn-outline gap-1" onClick={() => refetch()}>
              <RefreshCw size={14} /> Refresh
            </button>
          </div>
        </div>

        {agents.length === 0 && (
          <motion.div
            initial={{ opacity: 0, scale: 0.98 }}
            animate={{ opacity: 1, scale: 1 }}
            className="card bg-base-200 p-6 space-y-4 border border-success/20"
          >
            <div className="flex items-start gap-4">
              <div className="bg-success/10 p-3 rounded-xl text-success"><Zap size={24} /></div>
              <div>
                <h2 className="font-bold text-lg">Quick Start</h2>
                <p className="text-sm text-base-content/60">No agents yet. Build and run your first agent in one click.</p>
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              <button className="btn btn-success gap-2" onClick={() => navigate('/builder')}>
                <Plus size={16} /> Build first agent
              </button>
            </div>
          </motion.div>
        )}

        <section className="space-y-4">
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <Card className="p-5" hover>
              <CardMetric value={`${online}`} label="Agents Online" trend={`${offline} offline · ${idle} idle`} />
              <div className="mt-3 flex gap-1">
                {agents.slice(0, 5).map((a) => (
                  <div key={a.id} className={`w-1.5 h-6 rounded-full ${a.status === 'online' ? 'bg-emerald-500' : a.status === 'offline' ? 'bg-rose-500' : 'bg-amber-500'}`} />
                ))}
              </div>
            </Card>
            <Card className="p-5" hover>
              <CardMetric value={completed + failed + queued} label="Tasks" trend={`${running} running · ${completed} done · ${failed} failed`} color="text-warning" />
            </Card>
            <Card className="p-5" hover>
              <CardMetric value={credCount} label="Credentials" trend="harvested" color="text-error" />
            </Card>
            <Card className="p-5" hover>
              <CardMetric value={findingCount} label="Findings" trend="tracked" color="text-orange-400" />
            </Card>
          </div>
        </section>

        {/* Live system + agent metrics (auto-refresh) */}
        <section className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <ServerMetricsWidget />
          <AgentMetricsWidget />
        </section>

        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold flex items-center gap-2"><Radio size={18} className="text-success animate-pulse" /> Live Terrain</h2>
            <div className="flex gap-1 bg-base-200 rounded-lg p-1">
              {(['all', 'online', 'idle', 'offline'] as const).map((f) => (
                <button
                  key={f}
                  onClick={() => setAgentFilter(f)}
                  className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${agentFilter === f ? 'bg-base-100 text-success shadow-sm' : 'text-base-content/50 hover:text-base-content'}`}
                >
                  {f[0].toUpperCase() + f.slice(1)} ({f === 'all' ? agents.length : agents.filter(a => a.status === f).length})
                </button>
              ))}
            </div>
          </div>

          <motion.div
            variants={container}
            initial="hidden"
            animate="show"
            className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4"
          >
            {filteredAgents.map((a: Agent) => (
              <motion.div key={a.id} variants={item}>
                <AgentCard agent={a} onClick={() => openAgent(a.id)} />
              </motion.div>
            ))}
            {filteredAgents.length === 0 && (
              <div className="col-span-full py-10 text-center text-base-content/40">
                No agents match this filter.
              </div>
            )}
          </motion.div>
        </section>

        <section className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <Card className="col-span-2 p-5" hover={false}>
            <h3 className="font-semibold text-sm mb-4 flex items-center gap-2"><Activity size={14} /> Agent Connections (24h)</h3>
            <ResponsiveContainer width="100%" height={180}>
              <LineChart data={connLine}>
                <XAxis dataKey="time" tick={{ fontSize: 10 }} />
                <YAxis tick={{ fontSize: 10 }} />
                <Tooltip contentStyle={{ background: 'rgba(0,0,0,0.8)', border: 'none', borderRadius: 8 }} />
                <Line type="monotone" dataKey="online" stroke="#22c55e" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </Card>

          <Card className="p-5" hover={false}>
            <h3 className="font-semibold text-sm mb-4">OS Distribution</h3>
            <ResponsiveContainer width="100%" height={180}>
              <PieChart>
                <Pie data={osDist} dataKey="value" cx="50%" cy="50%" outerRadius={60} label>
                  {osDist.map((entry, i) => (
                    <Cell key={i} fill={OS_COLORS[entry.name] || PIE_COLORS[i % PIE_COLORS.length]} />
                  ))}
                </Pie>
                <Legend />
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </Card>
        </section>

        <section className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <Card className="p-5" hover={false}>
            <h3 className="font-semibold text-sm mb-4">Top Modules</h3>
            <ResponsiveContainer width="100%" height={160}>
              <BarChart data={moduleBarData} layout="vertical">
                <XAxis type="number" tick={{ fontSize: 10 }} />
                <YAxis dataKey="name" type="category" tick={{ fontSize: 10 }} width={80} />
                <Tooltip />
                <Bar dataKey="count" fill="#22c55e" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </Card>

          <Card className="col-span-2 p-5" hover={false}>
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-semibold text-sm flex items-center gap-2"><Radio size={14} className="text-success animate-pulse" /> Live Activity Feed</h3>
              <span className="badge badge-success badge-sm gap-1 animate-pulse">● LIVE</span>
            </div>
            <div className="space-y-1 max-h-48 overflow-y-auto scrollbar-thin text-xs">
              {feed.length === 0 && <p className="text-base-content/40 py-4 text-center">Waiting for events…</p>}
              {feed.map((item) => {
                const Icon = item.icon
                return (
                  <div key={item.id} className="flex gap-3 items-start p-2 rounded-lg hover:bg-base-300/50 transition-colors">
                    <span className="text-base-content/40 shrink-0 font-mono">{item.ts}</span>
                    <Icon size={12} className={`shrink-0 mt-0.5 ${item.color}`} />
                    <span className="text-base-content/80 break-all flex-1">{item.message}</span>
                  </div>
                )
              })}
            </div>
          </Card>
        </section>

        {/* Heatmap */}
        <section>
          <HeatmapCard />
        </section>

        <section className="space-y-3">
          <h2 className="text-lg font-bold">Quick Actions</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <QuickAction icon={Zap} label="Quick Recon" description="Run default recon timeline" color="success" onClick={handleQuickRecon} />
            <QuickAction icon={Terminal} label="Broadcast Shell" description="Send shell command to all agents" color="info" onClick={() => navigate('/terminal')} />
            <QuickAction icon={Bell} label="Alerts" description="Review unread notifications" color="warning" onClick={() => navigate('/alerts')} />
            <QuickAction icon={FileText} label="Report" description="Generate mission report" color="ghost" onClick={() => navigate('/reports')} />
          </div>
        </section>
      </div>
    </PageTransition>
  )
}
