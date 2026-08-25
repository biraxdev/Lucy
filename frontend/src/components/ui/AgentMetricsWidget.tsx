import { useQuery } from '@tanstack/react-query'
import { Cpu, MemoryStick, Activity } from 'lucide-react'
import api from '../../api/client'

interface AgentMetric {
  id: string
  hostname: string
  status: string
  cpu_percent: number | null
  ram_total_mb: number | null
  ram_available_mb: number | null
  ram_used_pct: number | null
}

function MetricBar({ label, value, icon: Icon, color }: { label: string; value: number | null; icon: React.ElementType; color: string }) {
  const pct = value ?? 0
  const barColor = pct >= 80 ? 'bg-error' : pct >= 50 ? 'bg-warning' : color
  return (
    <div className="flex items-center gap-2">
      <Icon size={11} className="text-base-content/40 shrink-0" />
      <span className="text-[10px] text-base-content/50 w-8 shrink-0">{label}</span>
      <div className="flex-1 h-1.5 bg-base-300 rounded-full overflow-hidden min-w-[40px]">
        <div className={`h-full rounded-full transition-all duration-500 ${barColor}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-[10px] font-mono text-base-content/60 w-10 text-right shrink-0">
        {value !== null ? `${pct.toFixed(0)}%` : '—'}
      </span>
    </div>
  )
}

export default function AgentMetricsWidget() {
  const { data: metrics = [] } = useQuery<AgentMetric[]>({
    queryKey: ['agent-metrics'],
    queryFn: () => api.get<AgentMetric[]>('/monitor/agents/metrics').then(r => r.data),
    refetchInterval: 5_000,
  })

  const online = metrics.filter(m => m.status === 'online')

  if (online.length === 0) {
    return (
      <div className="card bg-base-200 p-5">
        <h3 className="font-semibold text-sm mb-3 flex items-center gap-2">
          <Activity size={14} className="text-success" /> Agent CPU / RAM
        </h3>
        <p className="text-xs text-base-content/40 py-4 text-center">No online agents reporting metrics.</p>
      </div>
    )
  }

  return (
    <div className="card bg-base-200 p-5">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-semibold text-sm flex items-center gap-2">
          <Activity size={14} className="text-success animate-pulse" /> Agent CPU / RAM
        </h3>
        <span className="badge badge-success badge-xs gap-1 animate-pulse">● LIVE</span>
      </div>
      <div className="space-y-2 max-h-56 overflow-y-auto scrollbar-thin">
        {online.map(m => (
          <div key={m.id} className="space-y-1 p-2 rounded-lg hover:bg-base-300/50 transition-colors">
            <p className="text-xs font-mono truncate text-base-content/70">{m.hostname}</p>
            <MetricBar label="CPU" value={m.cpu_percent} icon={Cpu} color="bg-success" />
            <MetricBar label="RAM" value={m.ram_used_pct} icon={MemoryStick} color="bg-info" />
          </div>
        ))}
      </div>
    </div>
  )
}
