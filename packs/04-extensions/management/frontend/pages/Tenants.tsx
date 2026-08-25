import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Building2, Plus, Trash2, RefreshCw, Users, X,
  Server, KeyRound, ListTodo, Bug,
} from 'lucide-react'
import {
  listTenants, createTenant, deleteTenant,
  getTenantStats, listTenantMembers, assignUser, removeUser,
} from '../api/tenants'
import type { Tenant } from '../api/tenants'

// ---------------------------------------------------------------------------
// Create Tenant Modal
// ---------------------------------------------------------------------------

function CreateModal({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient()
  const [name, setName]   = useState('')
  const [slug, setSlug]   = useState('')
  const [desc, setDesc]   = useState('')
  const [color, setColor] = useState('#6366f1')

  const mut = useMutation({
    mutationFn: createTenant,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['tenants'] }); onClose() },
  })

  const autoSlug = (n: string) =>
    n.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9\-]/g, '').slice(0, 32)

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="bg-base-100 border border-base-300 rounded-2xl shadow-2xl w-full max-w-md p-6">
        <div className="flex items-center justify-between mb-5">
          <h2 className="font-bold text-lg flex items-center gap-2"><Building2 size={18}/> New Tenant</h2>
          <button className="btn btn-ghost btn-sm" onClick={onClose}><X size={16}/></button>
        </div>
        <form
          onSubmit={(e) => { e.preventDefault(); mut.mutate({ name, slug, description: desc, color }) }}
          className="space-y-3"
        >
          <label className="block">
            <span className="text-xs text-base-content/50">Team Name</span>
            <input className="input input-bordered input-sm w-full mt-1"
              value={name} required
              onChange={e => { setName(e.target.value); setSlug(autoSlug(e.target.value)) }}
              placeholder="Red Team Alpha" />
          </label>
          <label className="block">
            <span className="text-xs text-base-content/50">Slug (URL-safe identifier)</span>
            <input className="input input-bordered input-sm w-full mt-1 font-mono"
              value={slug} required
              onChange={e => setSlug(e.target.value)}
              placeholder="red-team-alpha" />
          </label>
          <label className="block">
            <span className="text-xs text-base-content/50">Description</span>
            <textarea className="textarea textarea-bordered w-full mt-1 text-sm" rows={2}
              value={desc} onChange={e => setDesc(e.target.value)} />
          </label>
          <label className="flex items-center gap-3">
            <span className="text-xs text-base-content/50">Accent color</span>
            <input type="color" className="w-10 h-8 rounded cursor-pointer border border-base-300"
              value={color} onChange={e => setColor(e.target.value)} />
            <span className="font-mono text-xs">{color}</span>
          </label>
          <div className="flex justify-end gap-2 pt-2">
            <button type="button" className="btn btn-ghost btn-sm" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn btn-primary btn-sm gap-1" disabled={mut.isPending}>
              {mut.isPending ? <span className="loading loading-spinner loading-xs"/> : <Plus size={14}/>}
              Create
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Tenant Detail Panel
// ---------------------------------------------------------------------------

function TenantDetail({ tenant, onClose }: { tenant: Tenant; onClose: () => void }) {
  const qc = useQueryClient()
  const [newUserId, setNewUserId] = useState('')
  const [newRole, setNewRole]     = useState('operator')

  const { data: stats } = useQuery({
    queryKey: ['tenant-stats', tenant.id],
    queryFn: () => getTenantStats(tenant.id),
  })

  const { data: members = [] } = useQuery({
    queryKey: ['tenant-members', tenant.id],
    queryFn: () => listTenantMembers(tenant.id),
  })

  const assignMut = useMutation({
    mutationFn: ({ uid, role }: { uid: string; role: string }) =>
      assignUser(tenant.id, uid, role),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['tenant-members', tenant.id] }); setNewUserId('') },
  })

  const removeMut = useMutation({
    mutationFn: (uid: string) => removeUser(tenant.id, uid),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['tenant-members', tenant.id] }),
  })

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="bg-base-100 border border-base-300 rounded-2xl shadow-2xl w-full max-w-xl p-6 space-y-5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-4 h-4 rounded-full" style={{ backgroundColor: tenant.color }} />
            <h2 className="font-bold text-lg">{tenant.name}</h2>
            <span className="badge badge-sm badge-outline font-mono">{tenant.slug}</span>
          </div>
          <button className="btn btn-ghost btn-sm" onClick={onClose}><X size={16}/></button>
        </div>

        {stats && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {[
              { icon: <Server size={14}/>,   label: 'Agents',      val: stats.agents },
              { icon: <ListTodo size={14}/>, label: 'Tasks',       val: stats.tasks },
              { icon: <KeyRound size={14}/>, label: 'Credentials', val: stats.credentials },
              { icon: <Bug size={14}/>,      label: 'Findings',    val: stats.findings },
            ].map(s => (
              <div key={s.label} className="bg-base-200 rounded-xl p-3 text-center">
                <div className="flex items-center justify-center gap-1 text-base-content/50 mb-1">{s.icon}<span className="text-xs">{s.label}</span></div>
                <p className="text-xl font-bold">{s.val}</p>
              </div>
            ))}
          </div>
        )}

        <div className="space-y-2">
          <h3 className="font-semibold flex items-center gap-2 text-sm"><Users size={14}/> Members ({members.length})</h3>
          <div className="space-y-1 max-h-40 overflow-y-auto">
            {members.map((m: any) => (
              <div key={m.id} className="flex items-center justify-between bg-base-200 rounded-lg px-3 py-2">
                <div>
                  <span className="font-mono text-sm">{m.username}</span>
                  <span className={`badge badge-xs ml-2 ${m.role === 'admin' ? 'badge-warning' : 'badge-ghost'}`}>{m.role}</span>
                </div>
                <button className="btn btn-ghost btn-xs text-error" onClick={() => removeMut.mutate(m.id)}>
                  <X size={12}/>
                </button>
              </div>
            ))}
            {members.length === 0 && <p className="text-xs text-base-content/40 text-center py-3">No members assigned</p>}
          </div>

          <div className="flex gap-2 pt-1">
            <input className="input input-bordered input-xs flex-1 font-mono"
              placeholder="User ID…" value={newUserId} onChange={e => setNewUserId(e.target.value)} />
            <select className="select select-bordered select-xs" value={newRole} onChange={e => setNewRole(e.target.value)}>
              {['admin', 'operator', 'viewer'].map(r => <option key={r}>{r}</option>)}
            </select>
            <button
              className="btn btn-xs btn-primary gap-1"
              disabled={!newUserId || assignMut.isPending}
              onClick={() => assignMut.mutate({ uid: newUserId, role: newRole })}
            >
              <Plus size={11}/> Add
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export default function Tenants() {
  const qc = useQueryClient()
  const [showCreate, setShowCreate] = useState(false)
  const [selected, setSelected]     = useState<Tenant | null>(null)

  const { data: tenants = [], isLoading, refetch } = useQuery({
    queryKey: ['tenants'],
    queryFn: listTenants,
  })

  const deleteMut = useMutation({
    mutationFn: deleteTenant,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['tenants'] }),
  })

  return (
    <div className="page-container space-y-5">
      {showCreate && <CreateModal onClose={() => setShowCreate(false)} />}
      {selected && <TenantDetail tenant={selected} onClose={() => setSelected(null)} />}

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Building2 size={22} className="text-indigo-400" /> Tenants
          </h1>
          <p className="text-sm text-base-content/50 mt-0.5">Isolated Red Team workspaces</p>
        </div>
        <div className="flex gap-2">
          <button className="btn btn-ghost btn-sm" onClick={() => refetch()}><RefreshCw size={14}/></button>
          <button className="btn btn-primary btn-sm gap-1" onClick={() => setShowCreate(true)}>
            <Plus size={14}/> New Tenant
          </button>
        </div>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-16"><span className="loading loading-spinner loading-lg text-primary"/></div>
      ) : tenants.length === 0 ? (
        <div className="text-center py-16 text-base-content/30">
          <Building2 size={48} className="mx-auto mb-3 opacity-20"/>
          <p className="text-sm">No tenants yet. Create one to isolate a Red Team workspace.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {tenants.map(t => (
            <div
              key={t.id}
              className="card bg-base-200 border border-base-300 p-5 space-y-3 hover:border-primary/40 transition-colors cursor-pointer"
              onClick={() => setSelected(t)}
            >
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-3 h-10 rounded-full" style={{ backgroundColor: t.color }} />
                  <div>
                    <p className="font-semibold">{t.name}</p>
                    <p className="font-mono text-xs text-base-content/40">{t.slug}</p>
                  </div>
                </div>
                <span className={`badge badge-sm ${t.active ? 'badge-success' : 'badge-ghost'}`}>
                  {t.active ? 'active' : 'inactive'}
                </span>
              </div>

              {t.description && (
                <p className="text-xs text-base-content/50 line-clamp-2">{t.description}</p>
              )}

              <div className="flex items-center justify-between pt-1">
                <p className="text-xs text-base-content/30">
                  {new Date(t.created_at).toLocaleDateString()}
                </p>
                <button
                  className="btn btn-ghost btn-xs text-error"
                  onClick={(e) => { e.stopPropagation(); deleteMut.mutate(t.id) }}
                >
                  <Trash2 size={12}/>
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
