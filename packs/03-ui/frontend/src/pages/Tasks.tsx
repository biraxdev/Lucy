import { useState, useMemo, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { DndProvider, useDrag, useDrop } from 'react-dnd'
import { HTML5Backend } from 'react-dnd-html5-backend'
import { getTasks, cancelTask, createTask, updateTask } from '../api/tasks'
import { getAgents } from '../api/agents'
import { ListTodo, XCircle, RefreshCw, Search, Plus, X, Filter, ArrowRight } from 'lucide-react'
import { Card, CardMetric } from '../components/ui/Card'
import { TaskCard, TaskLike } from '../components/ui/TaskCard'
import { StatusBadge } from '../components/ui/StatusBadge'
import { MaaSBreadcrumb, ViewLabel } from '../components/ui/MaaSBreadcrumb'
import { PageTransition } from '../components/ui/PageTransition'
import { useToast } from '../contexts/ToastContext'
import { getStatusStyle } from '../lib/statusTheme'

const TASK_TYPE = 'task'

const COLUMNS: { status: string; label: string }[] = [
  { status: 'queued',    label: 'Queued' },
  { status: 'running',   label: 'Running' },
  { status: 'completed', label: 'Completed' },
  { status: 'failed',    label: 'Failed' },
  { status: 'cancelled', label: 'Cancelled' },
]

function DraggableTaskCard({
  task,
  onCancel,
  onRerun,
  onClick,
}: {
  task: TaskLike
  onCancel: (task: TaskLike) => void
  onRerun: (task: TaskLike) => void
  onClick: (task: TaskLike) => void
}) {
  const [{ isDragging }, drag] = useDrag(() => ({
    type: TASK_TYPE,
    item: { id: task.id, status: task.status },
    collect: (monitor) => ({ isDragging: monitor.isDragging() }),
  }))

  return (
    <div
      ref={drag}
      onClick={() => onClick(task)}
      className={`${isDragging ? 'opacity-40' : 'opacity-100'} cursor-grab active:cursor-grabbing transition-opacity`}
    >
      <TaskCard task={task} onCancel={() => onCancel(task)} onRerun={() => onRerun(task)} />
    </div>
  )
}

function DropColumn({
  status,
  label,
  children,
  onDrop,
  isOver,
}: {
  status: string
  label: string
  children: React.ReactNode
  onDrop: (taskId: string, newStatus: string) => void
  isOver?: boolean
}) {
  const [{ canDrop, hovered }, drop] = useDrop(() => ({
    accept: TASK_TYPE,
    drop: (item: { id: string; status: string }) => onDrop(item.id, status),
    collect: (monitor) => ({
      canDrop: monitor.canDrop(),
      hovered: monitor.isOver(),
    }),
  }))

  const style = getStatusStyle(status)

  return (
    <div
      ref={drop}
      className={`rounded-2xl border transition-colors duration-200 ${
        hovered ? `${style.border} ${style.bg}` : 'border-base-300 bg-base-200/30'
      }`}
    >
      <div className="px-3 py-2 border-b border-base-300/50 flex items-center justify-between">
        <h3 className="text-xs font-bold uppercase tracking-wider flex items-center gap-2">
          <StatusBadge status={status} />
        </h3>
        <span className="text-[10px] text-base-content/40 font-mono">
          {Array.isArray(children) ? children.length : 0}
        </span>
      </div>
      <div className="p-3 space-y-3 min-h-[120px]">{children}</div>
    </div>
  )
}

function CreateTaskModal({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient()
  const toast = useToast()
  const { data: agents = [] } = useQuery({ queryKey: ['agents'], queryFn: getAgents })
  const [agentId, setAgentId]   = useState('')
  const [module, setModule]     = useState('shell')
  const [action, setAction]     = useState('exec')
  const [priority, setPriority] = useState('normal')
  const [params, setParams]     = useState('{}')
  const [paramsErr, setParamsErr] = useState(false)

  const mut = useMutation({
    mutationFn: createTask,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['tasks'] })
      toast.addToast({ type: 'success', title: 'Task dispatched', message: 'The task has been queued.' })
      onClose()
    },
    onError: (err: any) => {
      toast.addToast({ type: 'error', title: 'Dispatch failed', message: err?.message || 'Could not create task.' })
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    let parsed: Record<string, unknown> = {}
    try { parsed = JSON.parse(params); setParamsErr(false) } catch { setParamsErr(true); return }
    mut.mutate({ agent_id: agentId, module, action, priority: priority as any, params: parsed })
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.95 }}
        className="bg-base-100 border border-base-300 rounded-2xl shadow-2xl w-full max-w-md p-6"
      >
        <div className="flex items-center justify-between mb-5">
          <h2 className="font-bold text-lg flex items-center gap-2"><Plus size={18} /> New Task</h2>
          <button className="btn btn-ghost btn-sm" onClick={onClose}><X size={16} /></button>
        </div>
        <form onSubmit={handleSubmit} className="space-y-3">
          <label className="block">
            <span className="text-xs text-base-content/50">Agent</span>
            <select className="select select-bordered select-sm w-full mt-1" value={agentId}
              onChange={e => setAgentId(e.target.value)} required>
              <option value="">Select agent…</option>
              {agents.map((a: any) => (
                <option key={a.id} value={a.id}>{a.hostname} ({a.status})</option>
              ))}
            </select>
          </label>
          <div className="grid grid-cols-2 gap-3">
            <label className="block">
              <span className="text-xs text-base-content/50">Module</span>
              <input className="input input-bordered input-sm w-full mt-1 font-mono" value={module} onChange={e => setModule(e.target.value)} placeholder="shell" required />
            </label>
            <label className="block">
              <span className="text-xs text-base-content/50">Action</span>
              <input className="input input-bordered input-sm w-full mt-1" value={action} onChange={e => setAction(e.target.value)} placeholder="exec" required />
            </label>
          </div>
          <label className="block">
            <span className="text-xs text-base-content/50">Priority</span>
            <select className="select select-bordered select-sm w-full mt-1" value={priority} onChange={e => setPriority(e.target.value)}>
              {['critical','high','normal','low'].map(p => <option key={p}>{p}</option>)}
            </select>
          </label>
          <label className="block">
            <span className="text-xs text-base-content/50">Params (JSON)</span>
            <textarea className={`textarea textarea-bordered w-full mt-1 font-mono text-xs ${paramsErr ? 'textarea-error' : ''}`} rows={3} value={params} onChange={e => setParams(e.target.value)} />
            {paramsErr && <p className="text-error text-xs mt-1">Invalid JSON</p>}
          </label>
          <div className="flex justify-end gap-2 pt-2">
            <button type="button" className="btn btn-ghost btn-sm" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn btn-success btn-sm gap-1" disabled={mut.isPending}>
              {mut.isPending ? <span className="loading loading-spinner loading-xs" /> : <Plus size={14} />}
              Dispatch
            </button>
          </div>
        </form>
      </motion.div>
    </div>
  )
}

export default function Tasks() {
  const qc = useQueryClient()
  const navigate = useNavigate()
  const [search, setSearch] = useState('')
  const [showCreate, setShowCreate] = useState(false)

  const { data: tasks = [], isLoading, refetch } = useQuery({
    queryKey: ['tasks'],
    queryFn: () => getTasks({ limit: 500 }),
    refetchInterval: 5_000,
  })

  const toast = useToast()

  const cancelMut = useMutation({
    mutationFn: cancelTask,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['tasks'] })
      toast.addToast({ type: 'info', title: 'Task cancelled' })
    },
    onError: (err: any) => {
      toast.addToast({ type: 'error', title: 'Cancel failed', message: err?.message || 'Could not cancel task.' })
    },
  })

  const filtered = useMemo(() =>
    tasks.filter((t: any) =>
      [t.module, t.action, t.agent_id, t.status].some((v: any) =>
        String(v || '').toLowerCase().includes(search.toLowerCase())
      )
    ), [tasks, search])

  const grouped = useMemo(() => {
    const map: Record<string, any[]> = {}
    COLUMNS.forEach(c => map[c.status] = [])
    filtered.forEach((t: any) => {
      const key = t.status || 'queued'
      if (!map[key]) map[key] = []
      map[key].push(t)
    })
    return map
  }, [filtered])

  const counts = useMemo(() => {
    const out: Record<string, number> = {}
    COLUMNS.forEach(c => out[c.status] = grouped[c.status]?.length || 0)
    return out
  }, [grouped])

  const handleRerun = (task: TaskLike) => {
    createTask({ agent_id: task.agent_id, module: task.module, action: task.action, priority: task.priority as any, params: task.params || {} })
      .then(() => toast.addToast({ type: 'success', title: 'Task re-dispatched', message: `${task.module} › ${task.action}` }))
      .catch((err: any) => toast.addToast({ type: 'error', title: 'Rerun failed', message: err?.message || 'Could not rerun task.' }))
  }

  const updateMut = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) => updateTask(id, { status: status as any }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['tasks'] })
      toast.addToast({ type: 'success', title: 'Task moved' })
    },
    onError: (err: any) => {
      qc.invalidateQueries({ queryKey: ['tasks'] })
      toast.addToast({ type: 'error', title: 'Move failed', message: err?.message || 'Could not update task.' })
    },
  })

  const handleDrop = useCallback((taskId: string, newStatus: string) => {
    updateMut.mutate({ id: taskId, status: newStatus })
  }, [updateMut])

  const handleTaskClick = useCallback((task: TaskLike) => {
    navigate(`/tasks/${task.id}`)
  }, [navigate])

  return (
    <DndProvider backend={HTML5Backend}>
      <PageTransition>
        <div className="page-container space-y-6">
          {showCreate && <CreateTaskModal onClose={() => setShowCreate(false)} />}

          <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
            <div className="space-y-2">
              <MaaSBreadcrumb macro={{ label: 'Dashboard', to: '/' }} micro={{ label: 'Agents', to: '/agents' }} action={{ label: 'Tasks' }} />
              <ViewLabel type="action" label="Task Command" />
            </div>
            <div className="flex gap-2">
              <button className="btn btn-sm btn-success gap-1" onClick={() => setShowCreate(true)}><Plus size={14} /> Dispatch Task</button>
              <button className="btn btn-sm btn-outline gap-1" onClick={() => refetch()}><RefreshCw size={14} /> Refresh</button>
            </div>
          </div>

          <section className="grid grid-cols-2 md:grid-cols-5 gap-3">
            {COLUMNS.map(col => {
              const style = getStatusStyle(col.status)
              return (
                <Card key={col.status} hover className="p-4">
                  <CardMetric
                    value={counts[col.status]}
                    label={col.label}
                    color={style.text}
                    pulse={col.status === 'running' && counts[col.status] > 0}
                  />
                </Card>
              )
            })}
          </section>

          <section className="flex gap-2">
            <div className="relative flex-1 max-w-md">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-base-content/40" />
              <input
                className="input input-bordered w-full pl-8 input-sm"
                placeholder="Filter tasks by module, action, agent or status…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
            <div className="flex items-center gap-2 text-xs text-base-content/50">
              <Filter size={12} /> {filtered.length} task{filtered.length !== 1 ? 's' : ''}
              <span className="text-base-content/30 ml-2 hidden md:inline">· drag cards between columns · click for detail</span>
            </div>
          </section>

          {isLoading ? (
            <div className="flex justify-center py-12"><span className="loading loading-spinner loading-lg text-success" /></div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4 items-start">
              {COLUMNS.map((col) => {
                const colTasks = grouped[col.status] || []
                return (
                  <DropColumn
                    key={col.status}
                    status={col.status}
                    label={col.label}
                    onDrop={handleDrop}
                  >
                    {colTasks.length === 0 ? (
                      <div className="text-center py-6 text-base-content/30 text-xs border border-dashed border-base-300 rounded-xl">
                        No {col.label.toLowerCase()} tasks
                      </div>
                    ) : (
                      colTasks.map((t: any) => (
                        <DraggableTaskCard
                          key={t.id}
                          task={t}
                          onCancel={() => cancelMut.mutate(t.id)}
                          onRerun={handleRerun}
                          onClick={handleTaskClick}
                        />
                      ))
                    )}
                  </DropColumn>
                )
              })}
            </div>
          )}
        </div>
      </PageTransition>
    </DndProvider>
  )
}
