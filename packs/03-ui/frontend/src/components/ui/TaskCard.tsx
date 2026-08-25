import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { clsx } from 'clsx'
import {
  Play, RotateCcw, XCircle, ChevronDown, ChevronUp,
  Terminal, CheckCircle2, XCircle as XIcon, Clock, Loader2, Ban,
} from 'lucide-react'
import { Card, CardBody } from './Card'
import { StatusBadge } from './StatusBadge'
import { ProgressBar } from './ProgressBar'
import { getStatusStyle } from '../../lib/statusTheme'

export interface TaskLike {
  id: string
  module: string
  action: string
  agent_id?: string
  status: string
  priority: string
  params?: any
  result?: any
  error?: string
  created_at?: string
  executed_at?: string
}

interface TaskCardProps {
  task: TaskLike
  onRun?: (task: TaskLike) => void
  onCancel?: (task: TaskLike) => void
  onRerun?: (task: TaskLike) => void
  compact?: boolean
}

const STATUS_ICONS: Record<string, React.ElementType> = {
  queued: Clock,
  running: Loader2,
  completed: CheckCircle2,
  failed: XIcon,
  cancelled: Ban,
  pending: Clock,
}

const PRIORITY_STYLES: Record<string, string> = {
  critical: 'text-rose-400 bg-rose-500/10 border-rose-500/20',
  high: 'text-amber-400 bg-amber-500/10 border-amber-500/20',
  normal: 'text-sky-400 bg-sky-500/10 border-sky-500/20',
  low: 'text-base-content/50 bg-base-300 border-base-content/10',
}

export function TaskCard({ task, onRun, onCancel, onRerun, compact = false }: TaskCardProps) {
  const [expanded, setExpanded] = useState(false)
  const canAct = ['queued', 'running'].includes(task.status)
  const isRunning = task.status === 'running'
  const style = getStatusStyle(task.status)
  const StatusIcon = STATUS_ICONS[task.status] ?? Terminal

  // Estimate progress for running tasks based on elapsed time
  const progress = isRunning ? estimateProgress(task) : task.status === 'completed' ? 100 : task.status === 'failed' ? 100 : undefined

  return (
    <Card
      hover
      className={clsx('overflow-visible group', isRunning && 'task-running-shimmer')}
      onClick={() => setExpanded(!expanded)}
    >
      {/* Left accent bar — colored by status */}
      <div className={clsx('absolute left-0 top-0 bottom-0 w-1 bg-gradient-to-b', style.fill)} />

      <CardBody className="p-4 pl-5">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-3 min-w-0">
            {/* Status icon with animation */}
            <div className={clsx('w-9 h-9 rounded-lg flex items-center justify-center shrink-0 transition-colors', style.bg)}>
              <StatusIcon
                size={16}
                className={clsx(style.text, isRunning && 'animate-spin')}
              />
            </div>
            <div className="min-w-0">
              <h4 className="font-bold text-sm truncate">
                {task.module} <span className="text-base-content/50 font-normal">› {task.action}</span>
              </h4>
              <p className="text-[10px] text-base-content/50 font-mono truncate">
                {task.agent_id ? task.agent_id.slice(0, 8) + '…' : 'no agent'} · {task.created_at ? new Date(task.created_at).toLocaleString() : '—'}
              </p>
            </div>
          </div>
          <div className="flex flex-col items-end gap-1.5 shrink-0">
            <StatusBadge status={task.status} size="sm" />
            <span className={clsx(
              'text-[8px] uppercase tracking-wider font-bold px-1.5 py-0.5 rounded border',
              PRIORITY_STYLES[task.priority] ?? PRIORITY_STYLES.normal,
            )}>
              {task.priority}
            </span>
          </div>
        </div>

        {/* Progress bar for running/queued tasks */}
        {(isRunning || task.status === 'queued') && !compact && (
          <div className="mt-3">
            <ProgressBar
              value={isRunning ? progress : undefined}
              status={task.status}
              height="xs"
              shimmer={isRunning}
            />
          </div>
        )}

        {/* Completed/failed result preview */}
        {(task.status === 'completed' || task.status === 'failed') && !compact && (
          <div className={clsx(
            'mt-2 text-[10px] font-mono truncate px-2 py-1 rounded',
            task.status === 'completed' ? 'bg-emerald-500/5 text-emerald-400/70' : 'bg-rose-500/5 text-rose-400/70',
          )}>
            {task.status === 'completed'
              ? previewResult(task.result)
              : task.error || 'Task failed'}
          </div>
        )}

        {!compact && (
          <div className="flex items-center gap-2 mt-3" onClick={(e) => e.stopPropagation()}>
            {onRun && (
              <ActionBtn icon={Play} label="Run" color="success" onClick={() => onRun(task)} />
            )}
            {canAct && onCancel && (
              <ActionBtn icon={XCircle} label="Cancel" color="error" onClick={() => onCancel(task)} />
            )}
            {onRerun && task.status !== 'running' && (
              <ActionBtn icon={RotateCcw} label="Rerun" color="ghost" onClick={() => onRerun(task)} />
            )}
            <button
              onClick={(e) => { e.stopPropagation(); setExpanded(!expanded) }}
              className="btn btn-ghost btn-xs ml-auto gap-1 text-base-content/50 group-hover:text-success transition-colors"
            >
              {expanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
              {expanded ? 'Less' : 'Details'}
            </button>
          </div>
        )}

        <AnimatePresence>
          {expanded && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="overflow-hidden"
            >
              <div className="mt-3 pt-3 border-t border-base-300 space-y-2">
                {task.params && (
                  <div>
                    <p className="text-[10px] uppercase text-base-content/40 font-semibold">Params</p>
                    <pre className="text-[10px] font-mono bg-base-300/50 rounded p-2 overflow-x-auto">{JSON.stringify(task.params, null, 2)}</pre>
                  </div>
                )}
                {task.result && (
                  <div>
                    <p className="text-[10px] uppercase text-base-content/40 font-semibold">Result</p>
                    <pre className={clsx('text-[10px] font-mono rounded p-2 overflow-x-auto', style.bg, style.text)}>
                      {typeof task.result === 'string' ? task.result : JSON.stringify(task.result, null, 2)}
                    </pre>
                  </div>
                )}
                {task.error && (
                  <div>
                    <p className="text-[10px] uppercase text-base-content/40 font-semibold">Error</p>
                    <pre className="text-[10px] font-mono bg-rose-500/5 text-rose-400 rounded p-2 overflow-x-auto">{task.error}</pre>
                  </div>
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </CardBody>
    </Card>
  )
}

function ActionBtn({ icon: Icon, label, color, onClick }: { icon: React.ElementType; label: string; color: string; onClick: () => void }) {
  return (
    <motion.button
      whileHover={{ scale: 1.05 }}
      whileTap={{ scale: 0.95 }}
      onClick={onClick}
      className={`btn btn-xs btn-${color} gap-1`}
    >
      <Icon size={12} /> {label}
    </motion.button>
  )
}

/** Estimate progress based on elapsed time since execution */
function estimateProgress(task: TaskLike): number | undefined {
  if (!task.executed_at) return undefined
  const elapsed = Date.now() - new Date(task.executed_at).getTime()
  // Assume tasks take ~30s on average; cap at 90% until actually completed
  const pct = Math.min(90, (elapsed / 30_000) * 100)
  return pct
}

/** Short preview of task result */
function previewResult(result: any): string {
  if (!result) return 'No output'
  try {
    const parsed = typeof result === 'string' ? JSON.parse(result) : result
    if (parsed?.data) {
      const str = typeof parsed.data === 'string' ? parsed.data : JSON.stringify(parsed.data)
      return str.slice(0, 80) + (str.length > 80 ? '…' : '')
    }
    if (parsed?.error) return `Error: ${parsed.error}`
    const str = JSON.stringify(parsed)
    return str.slice(0, 80) + (str.length > 80 ? '…' : '')
  } catch {
    return String(result).slice(0, 80)
  }
}
