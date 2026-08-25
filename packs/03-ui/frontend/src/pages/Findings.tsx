import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Bug, Plus, Trash2, ChevronDown, ChevronUp, X,
  ShieldAlert, AlertTriangle, Info, CheckCircle, Loader2,
  Zap, ArrowRight,
} from 'lucide-react'
import api from '../api/client'
import { useToast } from '../contexts/ToastContext'

// ---------------------------------------------------------------------------
// Types & API
// ---------------------------------------------------------------------------

export type Severity = 'critical' | 'high' | 'medium' | 'low' | 'info'
export type FindingStatus = 'draft' | 'reviewed' | 'accepted' | 'mitigated' | 'false_positive'

export interface Finding {
  id: string
  title: string
  severity: Severity
  status: FindingStatus
  description: string
  recommendation: string
  evidence: string
  cvss: number | null
  agent_id: string | null
  created_at: string
  updated_at: string
}

const listFindings = () => api.get<Finding[]>('/findings').then(r => r.data)
const createFinding = (b: Partial<Finding>) => api.post<Finding>('/findings', b).then(r => r.data)
const updateFinding = (id: string, b: Partial<Finding>) => api.patch<Finding>(`/findings/${id}`, b).then(r => r.data)
const deleteFinding = (id: string) => api.delete(`/findings/${id}`)

// ---------------------------------------------------------------------------
// Severity & Status helpers
// ---------------------------------------------------------------------------

const SEV_STYLES: Record<Severity, string> = {
  critical: 'bg-red-500/15 text-red-400 border-red-500/30',
  high:     'bg-orange-500/15 text-orange-400 border-orange-500/30',
  medium:   'bg-yellow-500/15 text-yellow-400 border-yellow-500/30',
  low:      'bg-blue-500/15 text-blue-400 border-blue-500/30',
  info:     'bg-gray-500/15 text-gray-400 border-gray-500/30',
}
const SEV_ICON: Record<Severity, JSX.Element> = {
  critical: <ShieldAlert size={14} className="text-red-400" />,
  high:     <AlertTriangle size={14} className="text-orange-400" />,
  medium:   <AlertTriangle size={14} className="text-yellow-400" />,
  low:      <Info size={14} className="text-blue-400" />,
  info:     <Info size={14} className="text-gray-400" />,
}
const STATUS_STYLES: Record<FindingStatus, string> = {
  draft:          'badge-ghost',
  reviewed:       'badge-info',
  accepted:       'badge-warning',
  mitigated:      'badge-success',
  false_positive: 'badge-neutral',
}

const SEV_OPTIONS: Severity[]       = ['critical', 'high', 'medium', 'low', 'info']
const STATUS_OPTIONS: FindingStatus[] = ['draft', 'reviewed', 'accepted', 'mitigated', 'false_positive']

// ---------------------------------------------------------------------------
// Finding row (expandable)
// ---------------------------------------------------------------------------

function FindingRow({
  finding, onUpdate, onDelete,
}: {
  finding: Finding
  onUpdate: (id: string, data: Partial<Finding>) => void
  onDelete: (id: string) => void
}) {
  const [open, setOpen] = useState(false)
  const toast = useToast()

  const convertToTask = async (e: React.MouseEvent) => {
    e.stopPropagation()
    if (!finding.agent_id) {
      toast.addToast({ type: 'warning', title: 'No agent linked', message: 'This finding has no associated agent to dispatch a task to.' })
      return
    }
    try {
      const res = await api.post(`/findings/${finding.id}/to-task`, {
        module: 'shell',
        action: 'run',
        params: { cmd: 'echo "Investigating finding: ' + finding.title + '"' },
        priority: 'high',
      })
      toast.addToast({ type: 'success', title: 'Task dispatched', message: res.data?.message || 'Finding converted to task' })
      onUpdate(finding.id, { status: 'reviewed' })
    } catch (err: any) {
      toast.addToast({ type: 'error', title: 'Conversion failed', message: err?.message || 'Could not create task from finding' })
    }
  }

  return (
    <div className={`border rounded-lg overflow-hidden transition-all ${SEV_STYLES[finding.severity]}`}>
      <div
        className="flex items-center gap-3 px-4 py-3 cursor-pointer select-none"
        onClick={() => setOpen(o => !o)}
      >
        {SEV_ICON[finding.severity]}
        <div className="flex-1 min-w-0">
          <span className="font-medium text-sm">{finding.title}</span>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {finding.cvss !== null && (
            <span className="text-xs font-mono opacity-60">CVSS {finding.cvss.toFixed(1)}</span>
          )}
          <span className={`badge badge-xs ${STATUS_STYLES[finding.status]}`}>
            {finding.status.replace('_', ' ')}
          </span>
          <select
            className="select select-xs select-bordered opacity-70 w-28"
            value={finding.status}
            onClick={e => e.stopPropagation()}
            onChange={e => onUpdate(finding.id, { status: e.target.value as FindingStatus })}
          >
            {STATUS_OPTIONS.map(s => <option key={s} value={s}>{s.replace('_', ' ')}</option>)}
          </select>
          <button
            onClick={e => { e.stopPropagation(); onDelete(finding.id) }}
            className="btn btn-ghost btn-xs text-red-400"
          >
            <Trash2 size={12} />
          </button>
          {open ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </div>
      </div>

      {open && (
        <div className="px-4 pb-4 space-y-3 text-sm border-t border-current/10 mt-0 pt-3">
          <div>
            <p className="text-xs font-semibold opacity-50 uppercase mb-1">Description</p>
            <p className="opacity-80">{finding.description || '—'}</p>
          </div>
          <div>
            <p className="text-xs font-semibold opacity-50 uppercase mb-1">Evidence</p>
            <p className="font-mono text-xs opacity-70 bg-black/20 rounded p-2">{finding.evidence || '—'}</p>
          </div>
          <div>
            <p className="text-xs font-semibold opacity-50 uppercase mb-1">Recommendation</p>
            <p className="opacity-80">{finding.recommendation || '—'}</p>
          </div>
          {finding.agent_id && (
            <div className="flex items-center gap-2 pt-2 border-t border-current/10">
              <button
                onClick={convertToTask}
                className="btn btn-xs btn-success gap-1"
              >
                <Zap size={12} /> Convert to Task
                <ArrowRight size={10} />
              </button>
              <span className="text-[10px] opacity-40">Dispatch a task to agent {finding.agent_id.slice(0, 8)} to investigate this finding</span>
            </div>
          )}
          <p className="text-xs opacity-40">{finding.created_at?.slice(0, 19).replace('T', ' ')}</p>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// New finding modal
// ---------------------------------------------------------------------------

const EMPTY: Partial<Finding> = {
  title: '', severity: 'high', status: 'draft',
  description: '', recommendation: '', evidence: '', cvss: null,
}

function NewFindingModal({ onClose, onSave }: { onClose: () => void; onSave: (f: Partial<Finding>) => void }) {
  const [form, setForm] = useState({ ...EMPTY })
  const set = (k: keyof typeof EMPTY) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
    setForm(f => ({ ...f, [k]: e.target.value }))

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="bg-base-200 border border-base-300 rounded-xl w-full max-w-xl p-6 shadow-2xl space-y-4 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between">
          <h3 className="font-bold text-lg flex items-center gap-2"><Bug size={18}/> New Finding</h3>
          <button onClick={onClose} className="btn btn-ghost btn-sm btn-circle"><X size={16}/></button>
        </div>

        <div className="space-y-3">
          <div>
            <label className="text-xs text-base-content/50 mb-1 block">Title *</label>
            <input className="input input-bordered input-sm w-full" value={form.title} onChange={set('title')}
              placeholder="e.g. Browser passwords exposed without encryption" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-base-content/50 mb-1 block">Severity</label>
              <select className="select select-bordered select-sm w-full" value={form.severity} onChange={set('severity')}>
                {SEV_OPTIONS.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs text-base-content/50 mb-1 block">CVSS Score</label>
              <input className="input input-bordered input-sm w-full" type="number" min={0} max={10} step={0.1}
                value={form.cvss ?? ''} onChange={e => setForm(f => ({ ...f, cvss: e.target.value ? parseFloat(e.target.value) : null }))}
                placeholder="0.0 – 10.0" />
            </div>
          </div>
          <div>
            <label className="text-xs text-base-content/50 mb-1 block">Description</label>
            <textarea className="textarea textarea-bordered w-full text-sm" rows={3} value={form.description} onChange={set('description')}
              placeholder="Detailed description of the vulnerability..." />
          </div>
          <div>
            <label className="text-xs text-base-content/50 mb-1 block">Evidence</label>
            <textarea className="textarea textarea-bordered w-full text-sm font-mono" rows={2} value={form.evidence} onChange={set('evidence')}
              placeholder="Log output, file path, screenshot reference..." />
          </div>
          <div>
            <label className="text-xs text-base-content/50 mb-1 block">Recommendation</label>
            <textarea className="textarea textarea-bordered w-full text-sm" rows={2} value={form.recommendation} onChange={set('recommendation')}
              placeholder="How to fix or mitigate this finding..." />
          </div>
        </div>

        <div className="flex justify-end gap-2 pt-2">
          <button onClick={onClose} className="btn btn-ghost btn-sm">Cancel</button>
          <button
            onClick={() => { if (form.title) { onSave(form); onClose() } }}
            disabled={!form.title}
            className="btn btn-success btn-sm gap-1"
          >
            <Plus size={14}/> Create Finding
          </button>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function Findings() {
  const qc = useQueryClient()
  const [showModal, setShowModal] = useState(false)
  const [filter, setFilter] = useState<Severity | 'all'>('all')

  const { data: findings = [], isLoading } = useQuery({
    queryKey: ['findings'],
    queryFn: listFindings,
  })

  const doCreate = useMutation({
    mutationFn: createFinding,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['findings'] }),
  })

  const doUpdate = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<Finding> }) => updateFinding(id, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['findings'] }),
  })

  const doDelete = useMutation({
    mutationFn: deleteFinding,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['findings'] }),
  })

  const filtered = filter === 'all' ? findings : findings.filter(f => f.severity === filter)
  const counts = SEV_OPTIONS.reduce((acc, s) => ({ ...acc, [s]: findings.filter(f => f.severity === s).length }), {} as Record<Severity, number>)

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-5">
      {showModal && (
        <NewFindingModal
          onClose={() => setShowModal(false)}
          onSave={f => doCreate.mutate(f)}
        />
      )}

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Bug size={24} className="text-orange-400" /> Findings
          </h1>
          <p className="text-sm text-base-content/50 mt-1">Security findings & vulnerability tracking</p>
        </div>
        <button onClick={() => setShowModal(true)} className="btn btn-success btn-sm gap-1">
          <Plus size={14}/> New Finding
        </button>
      </div>

      {/* Severity summary */}
      <div className="flex gap-2 flex-wrap">
        <button onClick={() => setFilter('all')}
          className={`btn btn-xs ${filter === 'all' ? 'btn-primary' : 'btn-ghost'}`}>
          All ({findings.length})
        </button>
        {SEV_OPTIONS.map(s => (
          <button key={s} onClick={() => setFilter(s)}
            className={`btn btn-xs ${filter === s ? 'btn-active' : 'btn-ghost'} ${counts[s] ? '' : 'opacity-40'}`}>
            {s} ({counts[s] || 0})
          </button>
        ))}
      </div>

      {/* List */}
      {isLoading ? (
        <div className="flex justify-center py-12"><Loader2 size={28} className="animate-spin text-base-content/30" /></div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-16 text-base-content/30">
          <CheckCircle size={40} className="mx-auto mb-3 opacity-30" />
          <p className="text-sm">{filter === 'all' ? 'No findings yet. Create one manually or generate a report.' : `No ${filter} findings.`}</p>
        </div>
      ) : (
        <div className="space-y-2">
          {filtered.map(f => (
            <FindingRow
              key={f.id}
              finding={f}
              onUpdate={(id, data) => doUpdate.mutate({ id, data })}
              onDelete={id => doDelete.mutate(id)}
            />
          ))}
        </div>
      )}
    </div>
  )
}
