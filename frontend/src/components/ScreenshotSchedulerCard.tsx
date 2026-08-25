import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Camera, Play, Square, Zap, Settings2 } from 'lucide-react'
import api from '../api/client'

interface SchedulerStatus {
  running: boolean
  interval_minutes: number
  quality: number
  max_width: number
  target_mode: 'online' | 'all' | 'specific'
  target_agent_ids: string[]
  capture_count: number
  last_capture: Record<string, string>
}

export default function ScreenshotSchedulerCard() {
  const qc = useQueryClient()
  const [interval, setIntervalMin] = useState(5)
  const [quality, setQuality] = useState(70)
  const [maxWidth, setMaxWidth] = useState(1280)
  const [targetMode, setTargetMode] = useState<'online' | 'all' | 'specific'>('online')

  const { data: status, isLoading } = useQuery<SchedulerStatus>({
    queryKey: ['screenshot-scheduler'],
    queryFn: () => api.get<SchedulerStatus>('/screenshot-scheduler/status').then(r => r.data),
    refetchInterval: 5_000,
  })

  const configMut = useMutation({
    mutationFn: (cfg: Partial<SchedulerStatus>) =>
      api.put('/screenshot-scheduler/config', cfg).then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['screenshot-scheduler'] }),
  })

  const startMut = useMutation({
    mutationFn: () => api.post('/screenshot-scheduler/start').then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['screenshot-scheduler'] }),
  })

  const stopMut = useMutation({
    mutationFn: () => api.post('/screenshot-scheduler/stop').then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['screenshot-scheduler'] }),
  })

  const triggerMut = useMutation({
    mutationFn: () => api.post('/screenshot-scheduler/trigger').then(r => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['screenshot-scheduler'] }),
  })

  const applyConfig = () => {
    configMut.mutate({
      interval_minutes: interval,
      quality,
      max_width: maxWidth,
      target_mode: targetMode,
    })
  }

  const running = status?.running ?? false

  return (
    <div className="card bg-base-200 p-5 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="font-semibold flex items-center gap-2">
          <Camera size={16} /> Automatic Screenshots
        </h2>
        <span className={`badge badge-sm ${running ? 'badge-success animate-pulse' : 'badge-ghost'}`}>
          {running ? '● RUNNING' : 'STOPPED'}
        </span>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-4"><span className="loading loading-spinner loading-sm" /></div>
      ) : (
        <>
          {/* Stats */}
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div>
              <p className="text-xs text-base-content/50">Total captures</p>
              <p className="font-mono text-lg">{status?.capture_count ?? 0}</p>
            </div>
            <div>
              <p className="text-xs text-base-content/50">Agents captured</p>
              <p className="font-mono text-lg">{Object.keys(status?.last_capture ?? {}).length}</p>
            </div>
          </div>

          {/* Controls */}
          <div className="space-y-3">
            <label className="flex items-center justify-between gap-2 text-sm">
              <span className="text-base-content/60">Interval (min)</span>
              <input
                type="number" min={1} max={1440}
                className="input input-bordered input-xs w-20"
                value={interval}
                onChange={e => setIntervalMin(Number(e.target.value))}
                disabled={running}
              />
            </label>

            <label className="flex items-center justify-between gap-2 text-sm">
              <span className="text-base-content/60">Quality ({quality}%)</span>
              <input
                type="range" min={10} max={100} step={5}
                className="range range-xs range-success w-32"
                value={quality}
                onChange={e => setQuality(Number(e.target.value))}
                disabled={running}
              />
            </label>

            <label className="flex items-center justify-between gap-2 text-sm">
              <span className="text-base-content/60">Max width ({maxWidth}px)</span>
              <input
                type="number" min={320} max={3840} step={160}
                className="input input-bordered input-xs w-20"
                value={maxWidth}
                onChange={e => setMaxWidth(Number(e.target.value))}
                disabled={running}
              />
            </label>

            <label className="flex items-center justify-between gap-2 text-sm">
              <span className="text-base-content/60">Target</span>
              <select
                className="select select-bordered select-xs"
                value={targetMode}
                onChange={e => setTargetMode(e.target.value as any)}
                disabled={running}
              >
                <option value="online">Online agents</option>
                <option value="all">All agents</option>
                <option value="specific">Specific IDs</option>
              </select>
            </label>
          </div>

          {/* Actions */}
          <div className="flex gap-2 flex-wrap">
            {!running ? (
              <>
                <button
                  className="btn btn-sm btn-success gap-1"
                  onClick={() => { applyConfig(); startMut.mutate() }}
                  disabled={startMut.isPending}
                >
                  <Play size={12} /> Start
                </button>
                <button
                  className="btn btn-sm btn-outline gap-1"
                  onClick={applyConfig}
                  disabled={configMut.isPending}
                >
                  <Settings2 size={12} /> Apply config
                </button>
              </>
            ) : (
              <button
                className="btn btn-sm btn-error gap-1"
                onClick={() => stopMut.mutate()}
                disabled={stopMut.isPending}
              >
                <Square size={12} /> Stop
              </button>
            )}
            <button
              className="btn btn-sm btn-warning gap-1"
              onClick={() => triggerMut.mutate()}
              disabled={triggerMut.isPending}
            >
              <Zap size={12} /> Capture now
            </button>
          </div>
        </>
      )}
    </div>
  )
}
