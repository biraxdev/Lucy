/** DuplicateBadge — shows duplicate count and opens compare/merge dialog. */
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getDuplicates } from '../../api/library'
import { Copy, AlertTriangle, X, Check } from 'lucide-react'
import type { Resource } from '../../types/library'

export function DuplicateBadge({ resource }: { resource: Resource }) {
  const { data: dupData } = useQuery({
    queryKey: ['library-duplicates'],
    queryFn: getDuplicates,
  })

  const dupGroup = dupData?.duplicates.find(g =>
    g.content_hash === resource.content_hash && g.resources.some(r => r.id !== resource.id)
  )

  if (!dupGroup || dupGroup.resources.length <= 1) return null

  const duplicates = dupGroup.resources.filter(r => r.id !== resource.id)

  return (
    <div className="badge badge-sm badge-warning gap-1 cursor-pointer" title={`${duplicates.length} potential duplicate(s)`}>
      <Copy size={10} /> {duplicates.length} dup
    </div>
  )
}

export function DuplicateManager() {
  const { data, isLoading } = useQuery({
    queryKey: ['library-duplicates'],
    queryFn: getDuplicates,
  })
  const [selected, setSelected] = useState<DuplicateGroup | null>(null)

  if (isLoading) {
    return <div className="flex justify-center py-8"><span className="loading loading-spinner loading-sm text-success" /></div>
  }

  const groups = data?.duplicates ?? []

  if (groups.length === 0) {
    return (
      <div className="text-center py-8">
        <Check size={24} className="inline text-success mb-2" />
        <p className="text-sm text-base-content/40">No duplicates found</p>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <h4 className="text-xs font-semibold uppercase tracking-wide text-base-content/50 flex items-center gap-1">
        <AlertTriangle size={12} className="text-warning" /> {groups.length} duplicate group{groups.length !== 1 ? 's' : ''}
      </h4>

      {groups.map((group, i) => (
        <div key={i} className="card bg-base-200 p-3 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono text-base-content/40">hash: {group.content_hash?.slice(0, 12)}…</span>
            <span className="badge badge-xs badge-warning">{group.resources.length} copies</span>
          </div>
          <div className="space-y-1">
            {group.resources.map(r => (
              <div key={r.id} className="flex items-center gap-2 px-2 py-1.5 rounded-lg bg-base-300/50">
                <span className="badge badge-xs badge-success">{r.resource_type}</span>
                <span className="text-sm truncate flex-1">{r.name}</span>
                <span className="text-[10px] text-base-content/40">{r.status}</span>
                <span className="text-[10px] text-base-content/40 font-mono">{new Date(r.updated_at).toLocaleDateString()}</span>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

type DuplicateGroup = {
  content_hash: string
  resources: Resource[]
}
