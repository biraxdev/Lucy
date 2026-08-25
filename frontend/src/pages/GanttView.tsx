import { useQuery } from '@tanstack/react-query'
import { getTasks } from '../api/tasks'
import { BarChart2 } from 'lucide-react'

const STATUS_COLORS: Record<string, string> = {
  completed: '#22c55e', running: '#3b82f6', failed: '#ef4444',
  queued: '#6b7280', cancelled: '#f59e0b',
}

interface GanttRow {
  id: string; label: string; start: number; end: number; status: string; module: string
}

function msToLabel(ms: number): string {
  const d = new Date(ms)
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

export default function GanttView() {
  const { data: tasks = [] } = useQuery({
    queryKey: ['tasks-gantt'],
    queryFn: () => getTasks({ limit: 200 }),
    refetchInterval: 10000,
  })

  const rows: GanttRow[] = tasks
    .filter((t: any) => t.created_at)
    .map((t: any): GanttRow => {
      const start = new Date(t.created_at).getTime()
      const end = t.completed_at
        ? new Date(t.completed_at).getTime()
        : t.status === 'running' ? Date.now() : start + 5000
      return { id: t.id, label: `${t.module}:${t.action}`, start, end, status: t.status, module: t.module }
    })
    .sort((a: GanttRow, b: GanttRow) => a.start - b.start)

  const minTime = rows[0]?.start ?? Date.now()
  const maxTime = rows[rows.length - 1]?.end ?? Date.now() + 60000
  const totalMs = maxTime - minTime || 60000
  const BAR_HEIGHT = 28
  const LABEL_W = 160
  const CHART_W = 600

  return (
    <div className="page-container space-y-4">
      <h1 className="text-2xl font-bold flex items-center gap-2"><BarChart2 size={22} /> Gantt View</h1>

      {rows.length === 0 ? (
        <p className="text-base-content/40 text-sm">No tasks to display.</p>
      ) : (
        <div className="overflow-x-auto">
          <svg
            width={LABEL_W + CHART_W + 20}
            height={rows.length * (BAR_HEIGHT + 4) + 40}
            className="font-mono text-xs"
          >
            {/* Time axis ticks */}
            {Array.from({ length: 5 }).map((_, i) => {
              const x = LABEL_W + (i / 4) * CHART_W
              const t = minTime + (i / 4) * totalMs
              return (
                <g key={i}>
                  <line x1={x} y1={20} x2={x} y2={rows.length * (BAR_HEIGHT + 4) + 24} stroke="#374151" strokeDasharray="4,2" />
                  <text x={x} y={14} fill="#6b7280" textAnchor="middle">{msToLabel(t)}</text>
                </g>
              )
            })}

            {rows.map((row, i) => {
              const y = 24 + i * (BAR_HEIGHT + 4)
              const x = LABEL_W + ((row.start - minTime) / totalMs) * CHART_W
              const w = Math.max(4, ((row.end - row.start) / totalMs) * CHART_W)
              const color = STATUS_COLORS[row.status] ?? '#6b7280'
              return (
                <g key={row.id}>
                  <text x={LABEL_W - 6} y={y + BAR_HEIGHT / 2 + 4} fill="#9ca3af" textAnchor="end">
                    {row.label.length > 18 ? row.label.slice(0, 16) + '…' : row.label}
                  </text>
                  <rect x={x} y={y} width={w} height={BAR_HEIGHT} rx={4} fill={color} opacity={0.85} />
                  {w > 30 && (
                    <text x={x + 4} y={y + BAR_HEIGHT / 2 + 4} fill="white" fontSize={10}>
                      {row.status}
                    </text>
                  )}
                </g>
              )
            })}
          </svg>
        </div>
      )}

      <div className="flex gap-3 text-xs">
        {Object.entries(STATUS_COLORS).map(([s, c]) => (
          <span key={s} className="flex items-center gap-1">
            <span className="inline-block w-3 h-3 rounded" style={{ background: c }} />
            {s}
          </span>
        ))}
      </div>
    </div>
  )
}
