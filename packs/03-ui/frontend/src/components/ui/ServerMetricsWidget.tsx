import { useQuery } from '@tanstack/react-query'
import { Cpu, MemoryStick, Server, Activity } from 'lucide-react'
import api from '../../api/client'

interface ServerStats {
  system: {
    cpu_percent: number
    memory_used_mb: number
    memory_total_mb: number
    memory_percent: number
    platform: string
    uptime_seconds: number
  }
  agents: { total: number; online: number; offline: number }
  tasks: { queued: number; running: number; completed: number; failed: number }
  credentials: number
  logs: number
}

function fmtUptime(s: number): string {
  const h = Math.floor(s / 3600); const m = Math.floor((s % 3600) / 60); const sec = s % 60
  return `${h}h ${m}m ${sec}s`
}

export default function ServerMetricsWidget() {
  const { data } = useQuery<ServerStats>({
    queryKey: ['server-stats'],
    queryFn: () => api.get<ServerStats>('/monitor/stats').then(r => r.data),
    refetchInterval: 5_000,
  })

  if (!data) return null

  const sys = data.system
  const cpuColor = sys.cpu_percent >= 80 ? 'progress-error' : sys.cpu_percent >= 50 ? 'progress-warning' : 'progress-success'
  const ramColor = sys.memory_percent >= 80 ? 'progress-error' : sys.memory_percent >= 50 ? 'progress-warning' : 'progress-info'

  return (
    <div className="card bg-base-200 p-5 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-sm flex items-center gap-2">
          <Server size={14} className="text-success" /> C2 Server
        </h3>
        <span className="badge badge-success badge-xs gap-1 animate-pulse">● LIVE</span>
      </div>

      <div className="space-y-2">
        <div>
          <div className="flex items-center justify-between text-xs mb-1">
            <span className="flex items-center gap-1 text-base-content/60"><Cpu size={10} /> CPU</span>
            <span className="font-mono">{sys.cpu_percent.toFixed(1)}%</span>
          </div>
          <progress className={`progress ${cpuColor} w-full h-1.5`} value={sys.cpu_percent} max={100} />
        </div>

        <div>
          <div className="flex items-center justify-between text-xs mb-1">
            <span className="flex items-center gap-1 text-base-content/60"><MemoryStick size={10} /> RAM</span>
            <span className="font-mono">
              {sys.memory_used_mb.toFixed(0)} / {sys.memory_total_mb.toFixed(0)} MB ({sys.memory_percent.toFixed(1)}%)
            </span>
          </div>
          <progress className={`progress ${ramColor} w-full h-1.5`} value={sys.memory_percent} max={100} />
        </div>
      </div>

      <div className="grid grid-cols-3 gap-2 pt-1 text-center">
        <div>
          <p className="text-[10px] text-base-content/40">Agents</p>
          <p className="font-mono text-sm">
            <span className="text-success">{data.agents.online}</span>
            <span className="text-base-content/30"> / </span>
            <span>{data.agents.total}</span>
          </p>
        </div>
        <div>
          <p className="text-[10px] text-base-content/40">Tasks</p>
          <p className="font-mono text-sm">
            <span className="text-warning">{data.tasks.running}</span>
            <span className="text-base-content/30"> run</span>
          </p>
        </div>
        <div>
          <p className="text-[10px] text-base-content/40">Uptime</p>
          <p className="font-mono text-[10px]">{fmtUptime(sys.uptime_seconds)}</p>
        </div>
      </div>
    </div>
  )
}
