import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ShieldCheck, Users, Crown, Eye, Zap, Check, X } from 'lucide-react'
import api from '../api/client'
import { useToast } from '../contexts/ToastContext'
import { PageTransition } from '../components/ui/PageTransition'
import { Card } from '../components/ui/Card'
import { MaaSBreadcrumb, ViewLabel } from '../components/ui/MaaSBreadcrumb'

const roleIcons: Record<string, React.ElementType> = {
  superadmin: Crown,
  admin: ShieldCheck,
  operator: Zap,
  viewer: Eye,
}

const roleColors: Record<string, string> = {
  superadmin: 'text-rose-400 bg-rose-500/10 border-rose-500/30',
  admin: 'text-amber-400 bg-amber-500/10 border-amber-500/30',
  operator: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30',
  viewer: 'text-sky-400 bg-sky-500/10 border-sky-500/30',
}

export default function RBAC() {
  const qc = useQueryClient()
  const toast = useToast()

  const { data: roles = {} } = useQuery({
    queryKey: ['rbac-roles'],
    queryFn: () => api.get('/rbac/roles').then(r => r.data),
  })

  const { data: matrix } = useQuery({
    queryKey: ['rbac-matrix'],
    queryFn: () => api.get('/rbac/matrix').then(r => r.data),
  })

  const { data: users = [] } = useQuery({
    queryKey: ['rbac-users'],
    queryFn: () => api.get('/rbac/users').then(r => r.data),
  })

  const { data: me } = useQuery({
    queryKey: ['rbac-me'],
    queryFn: () => api.get('/rbac/me').then(r => r.data),
  })

  const updateRole = useMutation({
    mutationFn: ({ id, role }: { id: string; role: string }) =>
      api.put(`/rbac/users/${id}`, { role }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['rbac-users'] })
      toast.addToast({ type: 'success', title: 'Role updated', message: 'User role has been changed.' })
    },
    onError: () => toast.addToast({ type: 'error', title: 'Update failed' }),
  })

  return (
    <PageTransition>
      <div className="page-container space-y-6">
        <div className="space-y-2">
          <MaaSBreadcrumb macro={{ label: 'System', to: '/settings' }} />
          <ViewLabel type="macro" label="Roles & Access Control" />
        </div>

        {/* My permissions */}
        {me && (
          <Card className="p-5" hover={false}>
            <h3 className="font-semibold text-sm flex items-center gap-2 mb-3">
              <ShieldCheck size={14} className="text-success" /> Your Permissions
            </h3>
            <div className="flex items-center gap-3 mb-3">
              <span className={`badge badge-sm ${roleColors[me.role] || roleColors.viewer}`}>
                {me.role}
              </span>
              <span className="text-sm text-base-content/60">{me.username}</span>
            </div>
            <div className="flex flex-wrap gap-1">
              {me.permissions?.map((p: string) => (
                <span key={p} className="badge badge-xs badge-outline font-mono text-[9px]">
                  {p === '*' ? 'ALL PERMISSIONS' : p}
                </span>
              ))}
            </div>
          </Card>
        )}

        {/* Role-permission matrix */}
        {matrix && (
          <Card className="p-5" hover={false}>
            <h3 className="font-semibold text-sm flex items-center gap-2 mb-4">
              <Crown size={14} className="text-amber-400" /> Permission Matrix
            </h3>
            <div className="overflow-x-auto scrollbar-thin">
              <table className="table table-xs">
                <thead>
                  <tr>
                    <th className="text-left">Permission</th>
                    {matrix.roles?.map((r: string) => {
                      const Icon = roleIcons[r] || Eye
                      return (
                        <th key={r} className="text-center">
                          <div className="flex flex-col items-center gap-1">
                            <Icon size={12} className={roleColors[r]?.split(' ')[0]} />
                            <span className="text-[9px]">{r}</span>
                          </div>
                        </th>
                      )
                    })}
                  </tr>
                </thead>
                <tbody>
                  {matrix.permissions?.map((perm: string) => (
                    <tr key={perm} className="hover:bg-base-200">
                      <td className="font-mono text-[10px]">{perm}</td>
                      {matrix.roles?.map((r: string) => (
                        <td key={r} className="text-center">
                          {matrix.matrix?.[r]?.[perm] ? (
                            <Check size={12} className="text-emerald-400 inline" />
                          ) : (
                            <X size={12} className="text-base-content/20 inline" />
                          )}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        )}

        {/* Users list */}
        <Card className="p-5" hover={false}>
          <h3 className="font-semibold text-sm flex items-center gap-2 mb-4">
            <Users size={14} className="text-sky-400" /> Operators
          </h3>
          <div className="space-y-2">
            {users.map((u: any) => {
              const Icon = roleIcons[u.role] || Eye
              return (
                <div key={u.id} className="flex items-center gap-3 p-3 rounded-lg bg-base-200/50">
                  <div className="w-8 h-8 rounded-full bg-success/20 flex items-center justify-center text-xs font-bold text-success">
                    {u.username?.slice(0, 2).toUpperCase()}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium">{u.username}</p>
                    <p className="text-[10px] text-base-content/40 font-mono">{u.id.slice(0, 8)}</p>
                  </div>
                  <select
                    className="select select-xs select-bordered"
                    value={u.role}
                    onChange={e => updateRole.mutate({ id: u.id, role: e.target.value })}
                    disabled={me?.role === 'viewer'}
                  >
                    {Object.keys(roles).map(r => (
                      <option key={r} value={r}>{r}</option>
                    ))}
                  </select>
                  <Icon size={14} className={roleColors[u.role]?.split(' ')[0]} />
                </div>
              )
            })}
            {users.length === 0 && (
              <p className="text-center text-base-content/30 py-8 text-sm">No users found.</p>
            )}
          </div>
        </Card>
      </div>
    </PageTransition>
  )
}
