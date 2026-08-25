import { useState, useEffect, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ScrollText, Search, Trash2, RefreshCw, Filter, Download,
  AlertTriangle, Info, AlertOctagon, ChevronDown,
} from 'lucide-react'
import { listLogs, clearLogs } from '../api/logs'
import type { LogEntry } from '../api/logs'
import { useWebSocket } from '../hooks/useWebSocket'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const LEVEL_STYLES: Record<string, string> = {
  DEBUG:    'text-base-content/30',
  INFO:     'text-blue-400',
  WARN:     'text-yellow-400',
  WARNING:  'text-yellow-400',
  ERROR:    'text-red-400',
  CRITICAL: 'text-red-500 font-bold',
}
const LEVEL_BADGE: Record<string, string> = {
  DEBUG:    'badge-ghost',
  INFO:     'badge-info',
  WARN:     'badge-warning',
  WARNING:  'badge-warning',
  ERROR:    'badge-error',
  CRITICAL: 'badge-error',
}
const TYPE_BADGE: Record<string, string> = {
  system:   'badge-ghost',
  agent:    'badge-success',
  task:     'badge-info',
  module:   'badge-primary',
  security: 'badge-error',
}

const LEVELS  = ['DEBUG', 'INFO', 'WARN', 'ERROR', 'CRITICAL']
const TYPES   = ['system', 'agent', 'task', 'module', 'security']

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function Logs() {
  const qc = useQueryClient()
  const bottomRef = useRef<HTMLDivElement>(null)
  const [autoScroll, setAutoScroll] = useState(true)

  const [search,   setSearch]   = useState('')
  const [level,    setLevel]    = useState('')
  const [logType,  setLogType]  = useState('')
  const [agentId,  setAgentId]  = useState('')
  const [liveMode, setLiveMode] = useState(true)
  const [liveFeed, setLiveFeed] = useState<LogEntry[]>([])

  const params = {
    search: search || undefined,
    level: level || undefined,
    log_type: logType || undefined,
    agent_id: agentId || undefined,
    limit: 500,
  }

  const { data: logs = [], refetch } = useQuery({
    queryKey: ['logs', params],
    queryFn: () => listLogs(params),
    refetchInterval: liveMode ? 5000 : false,
  })

  const doClear = useMutation({
    mutationFn: clearLogs,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['logs'] })
      setLiveFeed([])
    },
  })

  // Live WS feed for new log entries
  const { on } = useWebSocket()
  useEffect(() => {
    return on('log', (msg: any) => {
      const payload = msg.payload as any
      const entry: LogEntry = {
        id: Math.random().toString(36).slice(2),
        agent_id: msg.agent_id || payload?.agent_id || null,
        level: payload?.level || 'INFO',
        module: payload?.module || 'agent',
        message: payload?.message || JSON.stringify(payload),
        log_type: 'agent',
        timestamp: new Date().toISOString(),
      }
      setLiveFeed(prev => [entry, ...prev].slice(0, 200))
    })
  }, [on])

  useEffect(() => {
    if (autoScroll && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [liveFeed, autoScroll])

  const handleExport = () => {
    const rows = [
      ['Timestamp', 'Level', 'Type', 'Module', 'Agent', 'Message'],
      ...displayLogs.map(l => [l.timestamp, l.level, l.log_type, l.module, l.agent_id || '', l.message]),
    ]
    const csv = rows.map(r => r.map(v => `"${v.replace(/"/g, '""')}"`).join(',')).join('\n')
    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a'); a.href = url; a.download = 'logs.csv'; a.click()
    URL.revokeObjectURL(url)
  }

  const displayLogs = liveMode
    ? [...liveFeed, ...logs].slice(0, 500)
    : logs

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <ScrollText size={24} className="text-purple-400" /> Audit Logs
          </h1>
          <p className="text-sm text-base-content/50 mt-1">{displayLogs.length} entries</p>
        </div>
        <div className="flex gap-2 items-center">
          <label className="flex items-center gap-1 cursor-pointer text-xs">
            <input type="checkbox" className="toggle toggle-xs toggle-success"
              checked={liveMode} onChange={e => setLiveMode(e.target.checked)} />
            Live
          </label>
          <button onClick={() => refetch()} className="btn btn-ghost btn-sm"><RefreshCw size={14} /></button>
          <button onClick={handleExport} className="btn btn-outline btn-sm gap-1">
            <Download size={14} /> Export
          </button>
          <button
            onClick={() => { if (confirm('Clear all logs?')) doClear.mutate() }}
            className="btn btn-error btn-sm gap-1"
          >
            <Trash2 size={14} /> Clear
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-base-200 border border-base-300 rounded-xl p-4">
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <label className="flex items-center gap-2 input input-bordered input-sm col-span-2 lg:col-span-1">
            <Search size={14} className="opacity-40 shrink-0" />
            <input className="grow bg-transparent outline-none" placeholder="Search messages…"
              value={search} onChange={e => setSearch(e.target.value)} />
          </label>
          <select className="select select-bordered select-sm" value={level} onChange={e => setLevel(e.target.value)}>
            <option value="">All levels</option>
            {LEVELS.map(l => <option key={l} value={l}>{l}</option>)}
          </select>
          <select className="select select-bordered select-sm" value={logType} onChange={e => setLogType(e.target.value)}>
            <option value="">All types</option>
            {TYPES.map(t => <option key={t} value={t}>{t}</option>)}
          </select>
          <input className="input input-bordered input-sm" placeholder="Filter by agent ID…"
            value={agentId} onChange={e => setAgentId(e.target.value)} />
        </div>
      </div>

      {/* Log list */}
      <div className="border border-base-300 rounded-xl overflow-hidden">
        {/* Level summary bar */}
        <div className="flex items-center gap-4 px-4 py-2 bg-base-200 border-b border-base-300 text-xs">
          {LEVELS.map(l => {
            const count = displayLogs.filter(e => e.level === l).length
            return count > 0 ? (
              <button key={l} onClick={() => setLevel(level === l ? '' : l)}
                className={`flex items-center gap-1 opacity-80 hover:opacity-100 ${level === l ? 'opacity-100 underline' : ''}`}>
                <span className={LEVEL_STYLES[l] || ''}>{l}</span>
                <span className="opacity-50">{count}</span>
              </button>
            ) : null
          })}
          <div className="flex-1" />
          <label className="flex items-center gap-1 cursor-pointer">
            <input type="checkbox" className="checkbox checkbox-xs"
              checked={autoScroll} onChange={e => setAutoScroll(e.target.checked)} />
            Auto-scroll
          </label>
        </div>

        <div className="max-h-[60vh] overflow-y-auto font-mono text-xs">
          {displayLogs.length === 0 ? (
            <div className="text-center py-12 text-base-content/30">
              <ScrollText size={32} className="mx-auto mb-2 opacity-30" />
              <p>No log entries match your filters.</p>
            </div>
          ) : (
            <table className="table table-xs w-full">
              <tbody>
                {displayLogs.map((log, i) => (
                  <tr key={log.id || i} className="hover border-b border-base-300/30">
                    <td className="opacity-40 whitespace-nowrap w-36 shrink-0">
                      {new Date(log.timestamp).toLocaleTimeString()}
                    </td>
                    <td className="w-20 shrink-0">
                      <span className={`badge badge-xs ${LEVEL_BADGE[log.level] || 'badge-ghost'}`}>
                        {log.level}
                      </span>
                    </td>
                    <td className="w-20 shrink-0">
                      <span className={`badge badge-xs ${TYPE_BADGE[log.log_type] || 'badge-ghost'}`}>
                        {log.log_type}
                      </span>
                    </td>
                    <td className="opacity-50 w-24 shrink-0 truncate">{log.module}</td>
                    <td className="opacity-30 w-24 shrink-0 truncate">{log.agent_id?.slice(0, 8)}</td>
                    <td className={`${LEVEL_STYLES[log.level] || ''} break-all`}>{log.message}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <div ref={bottomRef} />
        </div>
      </div>
    </div>
  )
}
