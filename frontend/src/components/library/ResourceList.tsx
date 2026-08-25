/** ResourceList — list view (compact rows). */
import { Star, Pin, Hash, Clock } from 'lucide-react'
import type { Resource } from '../../types/library'

const TYPE_COLORS: Record<string, string> = {
  module: 'text-info',
  poc: 'text-warning',
  cve: 'text-error',
  finding: 'text-error',
  playbook: 'text-accent',
  agent: 'text-success',
  note: 'text-base-content/60',
  script: 'text-info',
}

interface Props {
  resources: Resource[]
  onSelect: (r: Resource) => void
}

export default function ResourceList({ resources, onSelect }: Props) {
  return (
    <div className="space-y-1">
      {resources.map(r => (
        <div
          key={r.id}
          className="flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-base-200 cursor-pointer transition-all group"
          onClick={() => onSelect(r)}
        >
          <span className={`text-xs font-mono font-semibold w-32 shrink-0 ${TYPE_COLORS[r.resource_type] ?? 'text-base-content/60'}`}>
            {r.resource_type}
          </span>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium truncate group-hover:text-success transition-colors">
              {r.name}
            </p>
            {r.description && (
              <p className="text-xs text-base-content/50 truncate">{r.description}</p>
            )}
          </div>
          <div className="flex items-center gap-1.5 shrink-0">
            {r.tags?.slice(0, 2).map(t => (
              <span key={t} className="badge badge-xs badge-ghost gap-0.5">
                <Hash size={8} />{t}
              </span>
            ))}
          </div>
          <div className="flex items-center gap-1 shrink-0">
            {r.favorite && <Star size={12} className="text-warning" fill="currentColor" />}
            {r.pinned && <Pin size={12} className="text-info" fill="currentColor" />}
          </div>
          <span className="text-[10px] text-base-content/40 font-mono shrink-0 flex items-center gap-1">
            <Clock size={10} />
            {new Date(r.updated_at).toLocaleDateString()}
          </span>
        </div>
      ))}
    </div>
  )
}
