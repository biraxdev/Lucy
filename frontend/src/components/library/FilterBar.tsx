/** FilterBar — search + type/status/tag/visibility filters for the Library. */
import { useState, useMemo } from 'react'
import { Search, Filter, X, Star, Pin } from 'lucide-react'
import type { ResourceType, ResourceStatus, ResourceVisibility, LibraryFilters } from '../../types/library'

interface Props {
  filters: LibraryFilters & { q?: string }
  onChange: (filters: LibraryFilters & { q?: string }) => void
  types: Record<string, number>
  tags: string[]
}

const STATUS_OPTIONS: ResourceStatus[] = ['draft', 'experimental', 'active', 'stable', 'verified', 'deprecated', 'archived']
const VISIBILITY_OPTIONS: ResourceVisibility[] = ['public', 'internal', 'restricted', 'private']
const SORT_OPTIONS = [
  { value: 'updated_at', label: 'Last Updated' },
  { value: 'created_at', label: 'Newest' },
  { value: 'name', label: 'Name' },
  { value: 'use_count', label: 'Most Used' },
]

export default function FilterBar({ filters, onChange, types, tags }: Props) {
  const [showAdvanced, setShowAdvanced] = useState(false)

  const typeEntries = useMemo(
    () => Object.entries(types).sort((a, b) => b[1] - a[1]),
    [types],
  )

  const toggleType = (t: ResourceType) => {
    const current = filters.type ?? []
    const next = current.includes(t) ? current.filter(x => x !== t) : [...current, t]
    onChange({ ...filters, type: next.length ? next : undefined })
  }

  const toggleTag = (t: string) => {
    const current = filters.tag ?? []
    const next = current.includes(t) ? current.filter(x => x !== t) : [...current, t]
    onChange({ ...filters, tag: next.length ? next : undefined })
  }

  const toggleStatus = (s: ResourceStatus) => {
    const current = filters.status ?? []
    const next = current.includes(s) ? current.filter(x => x !== s) : [...current, s]
    onChange({ ...filters, status: next.length ? next : undefined })
  }

  const hasActiveFilters = filters.type || filters.tag || filters.status || filters.visibility || filters.favorite || filters.pinned

  return (
    <div className="space-y-3">
      {/* Search bar */}
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-base-content/40" />
          <input
            className="input input-bordered w-full pl-9 input-sm"
            placeholder="Search resources…"
            value={filters.q ?? ''}
            onChange={(e) => onChange({ ...filters, q: e.target.value })}
          />
        </div>
        <button
          className={`btn btn-sm gap-1 ${showAdvanced ? 'btn-success' : 'btn-ghost'}`}
          onClick={() => setShowAdvanced(!showAdvanced)}
        >
          <Filter size={14} /> Filters
          {hasActiveFilters && <span className="badge badge-xs badge-success ml-1">!</span>}
        </button>
        <button
          className={`btn btn-sm btn-ghost gap-1 ${filters.favorite ? 'text-warning' : ''}`}
          onClick={() => onChange({ ...filters, favorite: !filters.favorite })}
          title="Favorites only"
        >
          <Star size={14} fill={filters.favorite ? 'currentColor' : 'none'} />
        </button>
        <button
          className={`btn btn-sm btn-ghost gap-1 ${filters.pinned ? 'text-info' : ''}`}
          onClick={() => onChange({ ...filters, pinned: !filters.pinned })}
          title="Pinned only"
        >
          <Pin size={14} fill={filters.pinned ? 'currentColor' : 'none'} />
        </button>
      </div>

      {/* Type chips */}
      <div className="flex flex-wrap gap-1.5">
        {typeEntries.map(([type, count]) => {
          const active = filters.type?.includes(type as ResourceType)
          return (
            <button
              key={type}
              className={`badge badge-sm cursor-pointer gap-1 ${active ? 'badge-success' : 'badge-ghost'}`}
              onClick={() => toggleType(type as ResourceType)}
            >
              {type}
              <span className="opacity-50">{count}</span>
            </button>
          )
        })}
      </div>

      {/* Advanced filters */}
      {showAdvanced && (
        <div className="card bg-base-200 p-3 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wide text-base-content/50">Advanced Filters</span>
            {hasActiveFilters && (
              <button className="btn btn-xs btn-ghost gap-1" onClick={() => onChange({ q: filters.q })}>
                <X size={12} /> Clear
              </button>
            )}
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {/* Status */}
            <div>
              <label className="text-xs text-base-content/50 mb-1 block">Status</label>
              <div className="flex flex-wrap gap-1">
                {STATUS_OPTIONS.map(s => {
                  const active = filters.status?.includes(s)
                  return (
                    <button
                      key={s}
                      className={`badge badge-xs cursor-pointer ${active ? 'badge-success' : 'badge-ghost'}`}
                      onClick={() => toggleStatus(s)}
                    >
                      {s}
                    </button>
                  )
                })}
              </div>
            </div>

            {/* Visibility */}
            <div>
              <label className="text-xs text-base-content/50 mb-1 block">Visibility</label>
              <select
                className="select select-xs select-bordered"
                value={filters.visibility ?? ''}
                onChange={(e) => onChange({ ...filters, visibility: (e.target.value || undefined) as ResourceVisibility | undefined })}
              >
                <option value="">Any</option>
                {VISIBILITY_OPTIONS.map(v => <option key={v} value={v}>{v}</option>)}
              </select>
            </div>

            {/* Sort */}
            <div>
              <label className="text-xs text-base-content/50 mb-1 block">Sort</label>
              <select
                className="select select-xs select-bordered"
                value={filters.sort ?? 'updated_at'}
                onChange={(e) => onChange({ ...filters, sort: e.target.value as LibraryFilters['sort'] })}
              >
                {SORT_OPTIONS.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
              </select>
            </div>

            {/* Language */}
            <div>
              <label className="text-xs text-base-content/50 mb-1 block">Language</label>
              <input
                className="input input-xs input-bordered"
                placeholder="python, bash…"
                value={filters.language ?? ''}
                onChange={(e) => onChange({ ...filters, language: e.target.value || undefined })}
              />
            </div>
          </div>

          {/* Tags */}
          {tags.length > 0 && (
            <div>
              <label className="text-xs text-base-content/50 mb-1 block">Tags</label>
              <div className="flex flex-wrap gap-1">
                {tags.slice(0, 30).map(t => {
                  const active = filters.tag?.includes(t)
                  return (
                    <button
                      key={t}
                      className={`badge badge-xs cursor-pointer ${active ? 'badge-success' : 'badge-ghost'}`}
                      onClick={() => toggleTag(t)}
                    >
                      {t}
                    </button>
                  )
                })}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
