import { Handle, Position } from 'reactflow'
import { Play, Check, X, Loader2, Clock } from 'lucide-react'

export interface ModuleNodeData {
  module: string
  action: string
  params: Record<string, unknown>
  delay: number
  timeout: number
  priority: string
  description?: string
  status?: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled' | 'idle'
  taskId?: string
  result?: unknown
  error?: string
}

const STATUS_ICON: Record<string, React.ReactNode> = {
  queued: <Clock size={12} />,
  running: <Loader2 size={12} className="animate-spin" />,
  completed: <Check size={12} />,
  failed: <X size={12} />,
  cancelled: <X size={12} />,
  idle: <Play size={12} />,
}

const STATUS_COLOR: Record<string, string> = {
  queued: 'border-warning/60 text-warning',
  running: 'border-info/60 text-info',
  completed: 'border-success/60 text-success',
  failed: 'border-error/60 text-error',
  cancelled: 'border-error/60 text-error',
  idle: 'border-base-content/20 text-base-content/60',
}

export default function ModuleNode({ data, selected }: { data: ModuleNodeData; selected?: boolean }) {
  return (
    <div
      className={`bg-base-100 border-2 rounded-xl p-3 min-w-[180px] shadow-sm transition-all ${
        selected ? 'ring-2 ring-success border-success/50' : 'border-base-300'
      } ${STATUS_COLOR[data.status || 'idle']}`}
    >
      <Handle type="target" position={Position.Left} className="!bg-success" />
      <div className="flex items-center justify-between gap-2 mb-1">
        <span className="font-mono text-xs font-bold truncate">{data.module}</span>
        <span className="text-[10px] opacity-70">{STATUS_ICON[data.status || 'idle']}</span>
      </div>
      <div className="text-xs font-medium truncate">{data.action}</div>
      {data.description && (
        <div className="text-[10px] text-base-content/50 line-clamp-2 mt-1">{data.description}</div>
      )}
      <div className="flex gap-1 mt-2">
        <span className="badge badge-xs badge-ghost">{data.priority}</span>
        {data.delay > 0 && <span className="badge badge-xs badge-ghost">+{data.delay}s</span>}
      </div>
      <Handle type="source" position={Position.Right} className="!bg-success" />
    </div>
  )
}
