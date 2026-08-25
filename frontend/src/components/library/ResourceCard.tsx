/** ResourceCard — compact card preview for grid view. */
import { Star, Pin, Link2, Clock, Hash } from 'lucide-react'
import type { Resource } from '../../types/library'

const TYPE_COLORS: Record<string, string> = {
  module: 'badge-info',
  poc: 'badge-warning',
  cve: 'badge-error',
  finding: 'badge-error',
  evidence: 'badge-secondary',
  playbook: 'badge-accent',
  detection_rule: 'badge-primary',
  agent: 'badge-success',
  task: 'badge-ghost',
  credential_reference: 'badge-warning',
  note: 'badge-ghost',
  tactic: 'badge-secondary',
  technique: 'badge-secondary',
  script: 'badge-info',
  snippet: 'badge-ghost',
  documentation: 'badge-ghost',
}

const STATUS_COLORS: Record<string, string> = {
  draft: 'badge-ghost',
  experimental: 'badge-warning',
  active: 'badge-success',
  stable: 'badge-success',
  verified: 'badge-info',
  deprecated: 'badge-error',
  archived: 'badge-ghost',
  live: 'badge-info',
}

interface Props {
  resource: Resource
  onClick: () => void
}

export default function ResourceCard({ resource, onClick }: Props) {
  const typeBadge = TYPE_COLORS[resource.resource_type] ?? 'badge-ghost'
  const statusBadge = STATUS_COLORS[resource.status] ?? 'badge-ghost'

  return (
    <div
      className="card bg-base-200 hover:bg-base-300/50 cursor-pointer transition-all p-4 space-y-2 group"
      onClick={onClick}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className={`badge badge-sm ${typeBadge}`}>{resource.resource_type}</span>
          <span className={`badge badge-xs ${statusBadge}`}>{resource.status}</span>
          {resource._live && <span className="badge badge-xs badge-info animate-pulse">live</span>}
        </div>
        <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
          {resource.favorite && <Star size={12} className="text-warning" fill="currentColor" />}
          {resource.pinned && <Pin size={12} className="text-info" fill="currentColor" />}
        </div>
      </div>

      <h3 className="font-semibold text-sm line-clamp-1 group-hover:text-success transition-colors">
        {resource.name}
      </h3>

      {resource.description && (
        <p className="text-xs text-base-content/60 line-clamp-2">{resource.description}</p>
      )}

      {resource.tags?.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {resource.tags.slice(0, 4).map(t => (
            <span key={t} className="badge badge-xs badge-ghost gap-0.5">
              <Hash size={8} />{t}
            </span>
          ))}
          {resource.tags.length > 4 && <span className="text-xs text-base-content/40">+{resource.tags.length - 4}</span>}
        </div>
      )}

      <div className="flex items-center justify-between text-[10px] text-base-content/40 font-mono">
        <span className="flex items-center gap-1">
          <Clock size={10} />
          {new Date(resource.updated_at).toLocaleDateString()}
        </span>
        {resource.use_count > 0 && (
          <span className="flex items-center gap-1">
            <Link2 size={10} />{resource.use_count}
          </span>
        )}
      </div>
    </div>
  )
}
