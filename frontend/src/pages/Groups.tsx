import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Users, Plus, Trash2, Edit2, X, Check, RefreshCw,
  ChevronDown, ChevronUp, Zap, Users2, Database, Activity,
} from 'lucide-react'
import {
  listGroups, createGroup, updateGroup, deleteGroup,
  addMember, removeMember, resolveGroup, getAllGroupSummaries,
} from '../api/groups'
import type { AgentGroup, GroupSummary } from '../api/groups'
import { useQuery as useQ } from '@tanstack/react-query'
import api from '../api/client'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const COLOR_PRESETS = [
  '#22c55e', '#3b82f6', '#f59e0b', '#ef4444',
  '#8b5cf6', '#06b6d4', '#f97316', '#ec4899',
]

const QUERY_EXAMPLES = [
  'os = "windows"',
  'status = "online"',
  'os = "linux" AND status = "online"',
  'last_seen > NOW() - INTERVAL 1 HOUR',
  'username = "administrator"',
]

// ---------------------------------------------------------------------------
// Group form modal
// ---------------------------------------------------------------------------

interface GroupFormProps {
  initial?: AgentGroup | null
  agents: Array<{ id: string; hostname: string; os: string; status: string }>
  onClose: () => void
  onSave: (data: any) => void
}

function GroupForm({ initial, agents, onClose, onSave }: GroupFormProps) {
  const [name, setName]           = useState(initial?.name || '')
  const [desc, setDesc]           = useState(initial?.description || '')
  const [color, setColor]         = useState(initial?.color || '#22c55e')
  const [isDynamic, setIsDynamic] = useState(!!initial?.dynamic_query)
  const [query, setQuery]         = useState(initial?.dynamic_query || '')
  const [members, setMembers]     = useState<string[]>(initial?.members || [])

  const toggleAgent = (id: string) =>
    setMembers(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id])

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="bg-base-200 border border-base-300 rounded-xl w-full max-w-xl p-6 shadow-2xl space-y-4 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between">
          <h3 className="font-bold text-lg flex items-center gap-2">
            <Users size={18} /> {initial ? 'Edit Group' : 'New Group'}
          </h3>
          <button onClick={onClose} className="btn btn-ghost btn-sm btn-circle"><X size={16} /></button>
        </div>

        <div className="space-y-3">
          <div>
            <label className="text-xs text-base-content/50 mb-1 block">Name *</label>
            <input className="input input-bordered input-sm w-full" value={name}
              onChange={e => setName(e.target.value)} placeholder="e.g. Windows Servers" />
          </div>
          <div>
            <label className="text-xs text-base-content/50 mb-1 block">Description</label>
            <input className="input input-bordered input-sm w-full" value={desc}
              onChange={e => setDesc(e.target.value)} placeholder="Optional description" />
          </div>

          {/* Color */}
          <div>
            <label className="text-xs text-base-content/50 mb-1 block">Color</label>
            <div className="flex gap-2 flex-wrap">
              {COLOR_PRESETS.map(c => (
                <button key={c} onClick={() => setColor(c)}
                  className={`w-6 h-6 rounded-full border-2 transition-transform ${color === c ? 'border-white scale-125' : 'border-transparent'}`}
                  style={{ backgroundColor: c }} />
              ))}
            </div>
          </div>

          {/* Type toggle */}
          <div className="flex gap-2">
            <button onClick={() => setIsDynamic(false)}
              className={`btn btn-sm flex-1 gap-1 ${!isDynamic ? 'btn-primary' : 'btn-ghost'}`}>
              <Users2 size={14} /> Static
            </button>
            <button onClick={() => setIsDynamic(true)}
              className={`btn btn-sm flex-1 gap-1 ${isDynamic ? 'btn-primary' : 'btn-ghost'}`}>
              <Database size={14} /> Dynamic Query
            </button>
          </div>

          {isDynamic ? (
            <div>
              <label className="text-xs text-base-content/50 mb-1 block">Query</label>
              <textarea className="textarea textarea-bordered w-full text-sm font-mono" rows={2}
                value={query} onChange={e => setQuery(e.target.value)}
                placeholder='os = "windows" AND status = "online"' />
              <div className="flex gap-1 flex-wrap mt-1">
                {QUERY_EXAMPLES.map(ex => (
                  <button key={ex} onClick={() => setQuery(ex)}
                    className="btn btn-xs btn-ghost font-mono text-xs opacity-60 hover:opacity-100">
                    {ex}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div>
              <label className="text-xs text-base-content/50 mb-1 block">
                Agents ({members.length} selected)
              </label>
              <div className="max-h-44 overflow-y-auto space-y-1 border border-base-300 rounded-lg p-2">
                {agents.length === 0 && <p className="text-xs text-base-content/30 text-center py-2">No agents available</p>}
                {agents.map(a => (
                  <label key={a.id} className="flex items-center gap-2 cursor-pointer hover:bg-base-300 rounded px-2 py-1">
                    <input type="checkbox" className="checkbox checkbox-xs checkbox-success"
                      checked={members.includes(a.id)} onChange={() => toggleAgent(a.id)} />
                    <span className="text-xs font-mono flex-1">{a.hostname}</span>
                    <span className="text-xs opacity-40">{a.os}</span>
                    <span className={`badge badge-xs ${a.status === 'online' ? 'badge-success' : 'badge-ghost'}`}>{a.status}</span>
                  </label>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="flex justify-end gap-2 pt-2">
          <button onClick={onClose} className="btn btn-ghost btn-sm">Cancel</button>
          <button
            onClick={() => {
              if (!name) return
              onSave({ name, description: desc, color, dynamic_query: isDynamic ? query : '', members: isDynamic ? [] : members })
              onClose()
            }}
            disabled={!name}
            className="btn btn-success btn-sm gap-1"
          >
            <Check size={14} /> {initial ? 'Save' : 'Create'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Group card
// ---------------------------------------------------------------------------

function GroupCard({
  group, summary, onEdit, onDelete,
}: {
  group: AgentGroup
  summary?: GroupSummary
  onEdit: () => void
  onDelete: () => void
}) {
  const [open, setOpen]     = useState(false)
  const [resolved, setResolved] = useState<string[] | null>(null)
  const [loading, setLoading]   = useState(false)

  const handleResolve = async () => {
    if (resolved) { setResolved(null); return }
    setLoading(true)
    try {
      const r = await resolveGroup(group.id)
      setResolved(r.members)
    } finally {
      setLoading(false)
    }
  }

  const isDynamic = !!group.dynamic_query

  return (
    <div className="border border-base-300 rounded-xl overflow-hidden bg-base-200">
      <div className="flex items-center gap-3 px-4 py-3">
        <div className="w-3 h-3 rounded-full shrink-0" style={{ backgroundColor: group.color || '#22c55e' }} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <p className="font-medium text-sm">{group.name}</p>
            <span className={`badge badge-xs ${isDynamic ? 'badge-info' : 'badge-ghost'}`}>
              {isDynamic ? 'dynamic' : 'static'}
            </span>
          </div>
          {group.description && <p className="text-xs text-base-content/40 truncate">{group.description}</p>}
        </div>

        {/* Health summary stats (for 50+ agent fleets) */}
        {summary && (
          <div className="hidden sm:flex items-center gap-3 shrink-0 px-3 py-1 bg-base-300/50 rounded-lg">
            <div className="text-center">
              <p className="text-[9px] text-base-content/40 uppercase">Total</p>
              <p className="text-sm font-bold">{summary.total}</p>
            </div>
            <div className="text-center">
              <p className="text-[9px] text-success/60 uppercase">Online</p>
              <p className="text-sm font-bold text-success flex items-center gap-0.5">
                <Activity size={10} />{summary.online}
              </p>
            </div>
            <div className="text-center">
              <p className="text-[9px] text-warning/60 uppercase">Idle</p>
              <p className="text-sm font-bold text-warning">{summary.idle}</p>
            </div>
            <div className="text-center">
              <p className="text-[9px] text-error/60 uppercase">Off</p>
              <p className="text-sm font-bold text-error">{summary.offline}</p>
            </div>
          </div>
        )}

        <div className="flex items-center gap-1 shrink-0">
          <span className="text-xs text-base-content/40 mr-1">
            {isDynamic ? 'query' : `${(group.members || []).length} agents`}
          </span>
          <button onClick={handleResolve} disabled={loading}
            className="btn btn-ghost btn-xs gap-1" title="Resolve members">
            {loading ? <span className="loading loading-spinner loading-xs" /> : <Zap size={12} />}
            Resolve
          </button>
          <button onClick={onEdit} className="btn btn-ghost btn-xs"><Edit2 size={12} /></button>
          <button onClick={onDelete} className="btn btn-ghost btn-xs text-red-400"><Trash2 size={12} /></button>
          <button onClick={() => setOpen(o => !o)} className="btn btn-ghost btn-xs">
            {open ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </button>
        </div>
      </div>

      {open && (
        <div className="border-t border-base-300 px-4 py-3 space-y-2 text-xs">
          {isDynamic && (
            <div>
              <p className="text-base-content/50 font-semibold mb-1 uppercase">Query</p>
              <code className="block bg-black/20 rounded p-2 font-mono">{group.dynamic_query}</code>
            </div>
          )}
          {resolved !== null && (
            <div>
              <p className="text-base-content/50 font-semibold mb-1 uppercase">Resolved Members ({resolved.length})</p>
              {resolved.length === 0
                ? <p className="opacity-40">No agents match</p>
                : <div className="flex flex-wrap gap-1">
                    {resolved.map(id => (
                      <span key={id} className="badge badge-xs badge-ghost font-mono">{id.slice(0, 12)}</span>
                    ))}
                  </div>
              }
            </div>
          )}
          <p className="text-base-content/30">Created {new Date(group.created_at).toLocaleString()}</p>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function Groups() {
  const qc = useQueryClient()
  const [modal, setModal] = useState<'new' | AgentGroup | null>(null)

  const { data: groups = [], isLoading, refetch } = useQuery({
    queryKey: ['groups'],
    queryFn: listGroups,
  })

  const { data: groupSummaries = [] } = useQuery({
    queryKey: ['group-summaries'],
    queryFn: getAllGroupSummaries,
    refetchInterval: 30_000,
  })

  const { data: agentsRaw = [] } = useQ({
    queryKey: ['agents-list'],
    queryFn: () => api.get<any[]>('/agents').then(r => r.data),
  })

  const doCreate = useMutation({
    mutationFn: createGroup,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['groups'] }),
  })

  const doUpdate = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) => updateGroup(id, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['groups'] }),
  })

  const doDelete = useMutation({
    mutationFn: deleteGroup,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['groups'] }),
  })

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-5">
      {modal && (
        <GroupForm
          initial={modal === 'new' ? null : modal}
          agents={agentsRaw}
          onClose={() => setModal(null)}
          onSave={data => {
            if (modal === 'new') doCreate.mutate(data)
            else doUpdate.mutate({ id: (modal as AgentGroup).id, data })
          }}
        />
      )}

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Users size={24} className="text-blue-400" /> Agent Groups
          </h1>
          <p className="text-sm text-base-content/50 mt-1">Organize agents for timeline targeting</p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => refetch()} className="btn btn-ghost btn-sm gap-1">
            <RefreshCw size={14} />
          </button>
          <button onClick={() => setModal('new')} className="btn btn-success btn-sm gap-1">
            <Plus size={14} /> New Group
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="flex gap-4 text-sm">
        <span className="text-base-content/50">{groups.length} groups</span>
        <span className="text-base-content/50">{groups.filter(g => !!g.dynamic_query).length} dynamic</span>
        <span className="text-base-content/50">{groups.filter(g => !g.dynamic_query).length} static</span>
      </div>

      {/* List */}
      {isLoading ? (
        <div className="flex justify-center py-12">
          <span className="loading loading-spinner loading-lg text-base-content/30" />
        </div>
      ) : groups.length === 0 ? (
        <div className="text-center py-16 text-base-content/30">
          <Users size={40} className="mx-auto mb-3 opacity-30" />
          <p className="text-sm">No groups yet. Create one to target timelines at specific agent sets.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {groups.map(g => (
            <GroupCard
              key={g.id}
              group={g}
              summary={groupSummaries.find((s) => s.group_id === g.id)}
              onEdit={() => setModal(g)}
              onDelete={() => doDelete.mutate(g.id)}
            />
          ))}
        </div>
      )}
    </div>
  )
}
