import { ChevronRight, LayoutDashboard, Server, ListTodo } from 'lucide-react'
import { Link } from 'react-router-dom'
import { clsx } from 'clsx'

interface Crumb {
  label: string
  to?: string
  active?: boolean
}

export function MaaSBreadcrumb({
  macro,
  micro,
  action,
}: {
  macro?: { label?: string; to?: string }
  micro?: { label?: string; to?: string }
  action?: { label?: string }
}) {
  const crumbs: Crumb[] = [
    { label: macro?.label ?? 'Dashboard', to: macro?.to ?? '/', active: !micro && !action },
    ...(micro ? [{ label: micro.label ?? 'Agent', to: micro.to, active: !action }] : []),
    ...(action ? [{ label: action.label ?? 'Task', active: true }] : []),
  ]

  return (
    <nav className="flex items-center gap-2 text-sm text-base-content/50">
      <LayoutDashboard size={14} className="text-success" />
      {crumbs.map((crumb, i) => (
        <div key={crumb.label + i} className="flex items-center gap-2">
          {i > 0 && <ChevronRight size={14} className="text-base-content/30" />}
          {crumb.active || !crumb.to ? (
            <span className={clsx('font-medium', crumb.active ? 'text-base-content' : '')}>{crumb.label}</span>
          ) : (
            <Link to={crumb.to} className="hover:text-success transition-colors">{crumb.label}</Link>
          )}
        </div>
      ))}
    </nav>
  )
}

export function ViewLabel({ type, label }: { type: 'macro' | 'micro' | 'action'; label: string }) {
  const icons = { macro: LayoutDashboard, micro: Server, action: ListTodo }
  const Icon = icons[type]
  const colors = {
    macro: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20',
    micro: 'text-sky-400 bg-sky-500/10 border-sky-500/20',
    action: 'text-amber-400 bg-amber-500/10 border-amber-500/20',
  }
  const subtitles = {
    macro: 'Situation macro : vue d’ensemble du terrain',
    micro: 'Vue micro : focus sur un agent',
    action: 'Vue action : exécution et suivi des tâches',
  }
  return (
    <div className="flex items-start gap-3">
      <div className={clsx('p-2 rounded-xl border', colors[type])}>
        <Icon size={18} />
      </div>
      <div>
        <h1 className="text-2xl font-bold tracking-tight">{label}</h1>
        <p className="text-xs text-base-content/50">{subtitles[type]}</p>
      </div>
    </div>
  )
}
