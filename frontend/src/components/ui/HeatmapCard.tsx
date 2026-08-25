import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { motion } from 'framer-motion'
import { Activity, Clock, Server } from 'lucide-react'
import api from '../../api/client'
import { Card } from './Card'

interface HeatmapCell { x: number; y: string; v: number }
interface HeatmapData {
  mode: string
  x_label: string
  y_label: string
  x_axis: number[] | string[]
  y_axis: string[]
  max: number
  cells: HeatmapCell[]
}

export function HeatmapCard() {
  const [mode, setMode] = useState<'time' | 'agent'>('time')

  const { data, isLoading } = useQuery({
    queryKey: ['heatmap', mode],
    queryFn: () => api.get<HeatmapData>(`/monitor/heatmap?by=${mode}`).then((r: any) => r.data),
    refetchInterval: 60_000,
  })

  const max = data?.max || 1

  const colorFor = (v: number) => {
    if (v === 0) return 'bg-base-200'
    const intensity = Math.min(1, v / max)
    const opacity = 0.15 + intensity * 0.85
    return `bg-success`
  }

  const colorStyle = (v: number): React.CSSProperties => {
    if (v === 0) return {}
    const intensity = Math.min(1, v / max)
    return { backgroundColor: `rgba(34, 197, 94, ${0.15 + intensity * 0.85})` }
  }

  return (
    <Card className="p-5" hover={false}>
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold text-sm flex items-center gap-2">
          <Activity size={14} className="text-success" /> Activity Heatmap
        </h3>
        <div className="flex gap-1 bg-base-200 rounded-lg p-0.5">
          <button
            onClick={() => setMode('time')}
            className={`px-2 py-1 rounded-md text-[10px] font-medium transition-colors flex items-center gap-1 ${
              mode === 'time' ? 'bg-base-100 text-success shadow-sm' : 'text-base-content/50'
            }`}
          >
            <Clock size={10} /> Time
          </button>
          <button
            onClick={() => setMode('agent')}
            className={`px-2 py-1 rounded-md text-[10px] font-medium transition-colors flex items-center gap-1 ${
              mode === 'agent' ? 'bg-base-100 text-success shadow-sm' : 'text-base-content/50'
            }`}
          >
            <Server size={10} /> Agent
          </button>
        </div>
      </div>

      {isLoading && (
        <div className="flex justify-center py-10">
          <span className="loading loading-spinner loading-sm text-success" />
        </div>
      )}

      {data && !isLoading && (
        <div className="overflow-x-auto scrollbar-thin">
          <div className="inline-block min-w-full">
            {/* X axis labels */}
            <div className="flex gap-0.5 ml-12 mb-1">
              {data.x_axis.map((x: any, i: number) => (
                <div
                  key={i}
                  className="w-5 text-center text-[8px] text-base-content/30 font-mono"
                  style={{ minWidth: '20px' }}
                >
                  {typeof x === 'number' ? (x % 3 === 0 ? `${x}h` : '') : (x as string).slice(0, 3)}
                </div>
              ))}
            </div>
            {/* Rows */}
            {data.y_axis.map((y: string, yi: number) => (
              <div key={y} className="flex items-center gap-0.5 mb-0.5">
                <div className="w-12 text-[9px] text-base-content/40 truncate pr-1 text-right shrink-0">
                  {y.length > 8 ? y.slice(0, 8) + '…' : y}
                </div>
                {data.x_axis.map((_: any, xi: number) => {
                  const cell = data.cells.find((c: HeatmapCell) => c.x === xi && c.y === y)
                  const v = cell?.v || 0
                  return (
                    <motion.div
                      key={xi}
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      transition={{ delay: (xi + yi) * 0.002 }}
                      className="w-5 h-5 rounded-sm shrink-0"
                      style={{
                        minWidth: '20px',
                        ...colorStyle(v),
                      }}
                      title={`${y} · ${data.x_axis[xi]}: ${v} events`}
                    />
                  )
                })}
              </div>
            ))}
            {/* Legend */}
            <div className="flex items-center gap-2 mt-3 ml-12 text-[9px] text-base-content/40">
              <span>Less</span>
              {[0.15, 0.35, 0.55, 0.75, 0.95].map((o, i) => (
                <div
                  key={i}
                  className="w-3 h-3 rounded-sm"
                  style={{ backgroundColor: `rgba(34, 197, 94, ${o})` }}
                />
              ))}
              <span>More</span>
            </div>
          </div>
        </div>
      )}

      {data && data.cells.length > 0 && (
        <p className="text-[10px] text-base-content/40 mt-3">
          {data.x_label} × {data.y_label} — peak: {max} events
        </p>
      )}
    </Card>
  )
}
