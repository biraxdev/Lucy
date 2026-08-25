/** ResourceDetail — full detail view with tabs: Content, Relations, Versions, Suggestions. */
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  getResource, updateResource, deleteResource, getVersions,
  createVersion, restoreVersion, toggleFavorite, togglePin,
  duplicateResource, getSuggestions, exportResource,
} from '../../api/library'
import {
  Star, Pin, Trash2, Copy, Download, GitBranch, Sparkles, Save,
  FileText, Link2, Lightbulb, Eye, Clock, RotateCcw,
} from 'lucide-react'
import ResourcePreview from './ResourcePreview'
import RelationPanel from './RelationPanel'
import type { Resource } from '../../types/library'

interface Props {
  resourceId: string
  onClose: () => void
}

type Tab = 'preview' | 'content' | 'relations' | 'versions' | 'suggestions'

export default function ResourceDetail({ resourceId, onClose }: Props) {
  const qc = useQueryClient()
  const [tab, setTab] = useState<Tab>('preview')
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState<Partial<Resource>>({})

  const { data: resource, isLoading } = useQuery({
    queryKey: ['library-resource', resourceId],
    queryFn: () => getResource(resourceId),
  })

  const { data: versions = [] } = useQuery({
    queryKey: ['library-versions', resourceId],
    queryFn: () => getVersions(resourceId),
    enabled: tab === 'versions',
  })

  const { data: suggestions = [] } = useQuery({
    queryKey: ['library-suggestions', resourceId],
    queryFn: () => getSuggestions(resourceId),
    enabled: tab === 'suggestions',
  })

  const updateMut = useMutation({
    mutationFn: (data: Record<string, unknown>) => updateResource(resourceId, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['library-resource', resourceId] })
      setEditing(false)
      setDraft({})
    },
  })

  const favMut = useMutation({
    mutationFn: () => toggleFavorite(resourceId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['library-resource', resourceId] }),
  })

  const pinMut = useMutation({
    mutationFn: () => togglePin(resourceId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['library-resource', resourceId] }),
  })

  const dupMut = useMutation({
    mutationFn: () => duplicateResource(resourceId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['library'] }),
  })

  const delMut = useMutation({
    mutationFn: () => deleteResource(resourceId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['library'] })
      onClose()
    },
  })

  const versionMut = useMutation({
    mutationFn: (note: string) => createVersion(resourceId, note),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['library-versions', resourceId] }),
  })

  const restoreMut = useMutation({
    mutationFn: (vid: string) => restoreVersion(resourceId, vid),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['library-resource', resourceId] })
      qc.invalidateQueries({ queryKey: ['library-versions', resourceId] })
    },
  })

  const exportMut = useMutation({
    mutationFn: (format: 'json' | 'yaml' | 'md' | 'raw') => exportResource(resourceId, format),
    onSuccess: (data) => {
      const blob = new Blob([data.content], { type: data.content_type })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url; a.download = data.name; a.click()
      URL.revokeObjectURL(url)
    },
  })

  if (isLoading || !resource) {
    return (
      <div className="flex justify-center py-12">
        <span className="loading loading-spinner loading-lg text-success" />
      </div>
    )
  }

  const isRuntime = ['agent', 'task', 'credential_reference', 'log', 'timeline', 'group', 'redirector'].includes(resource.resource_type)
  const canEdit = !isRuntime && resource.resource_type !== 'cve'

  const tabs: { id: Tab; label: string; icon: React.ElementType }[] = [
    { id: 'preview', label: 'Preview', icon: Eye },
    { id: 'content', label: 'Content', icon: FileText },
    { id: 'relations', label: 'Relations', icon: Link2 },
    { id: 'versions', label: 'Versions', icon: GitBranch },
    { id: 'suggestions', label: 'AI', icon: Sparkles },
  ]

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="badge badge-sm badge-success">{resource.resource_type}</span>
            <span className="badge badge-xs badge-ghost">{resource.status}</span>
            <span className="badge badge-xs badge-ghost">v{resource.version}</span>
            {resource.visibility !== 'internal' && (
              <span className="badge badge-xs badge-warning">{resource.visibility}</span>
            )}
          </div>
          {editing ? (
            <input
              className="input input-bordered input-sm w-full"
              value={draft.name ?? resource.name}
              onChange={(e) => setDraft({ ...draft, name: e.target.value })}
            />
          ) : (
            <h2 className="text-xl font-bold truncate">{resource.name}</h2>
          )}
          {resource.description && !editing && (
            <p className="text-sm text-base-content/60 mt-1">{resource.description}</p>
          )}
          {editing && (
            <textarea
              className="textarea textarea-bordered textarea-sm w-full mt-1"
              placeholder="Description…"
              value={draft.description ?? resource.description ?? ''}
              onChange={(e) => setDraft({ ...draft, description: e.target.value })}
            />
          )}
        </div>
        <div className="flex gap-1 shrink-0">
          <button
            className={`btn btn-sm btn-ghost ${resource.favorite ? 'text-warning' : ''}`}
            onClick={() => favMut.mutate()}
            title="Favorite"
          >
            <Star size={14} fill={resource.favorite ? 'currentColor' : 'none'} />
          </button>
          <button
            className={`btn btn-sm btn-ghost ${resource.pinned ? 'text-info' : ''}`}
            onClick={() => pinMut.mutate()}
            title="Pin"
          >
            <Pin size={14} fill={resource.pinned ? 'currentColor' : 'none'} />
          </button>
          <div className="dropdown dropdown-end">
            <button tabIndex={0} className="btn btn-sm btn-ghost" title="Export">
              <Download size={14} />
            </button>
            <ul tabIndex={0} className="dropdown-content menu bg-base-200 rounded-box z-10 w-32 p-1 shadow-lg">
              <li><button onClick={() => exportMut.mutate('json')}>JSON</button></li>
              <li><button onClick={() => exportMut.mutate('yaml')}>YAML</button></li>
              <li><button onClick={() => exportMut.mutate('md')}>Markdown</button></li>
              <li><button onClick={() => exportMut.mutate('raw')}>Raw</button></li>
            </ul>
          </div>
          <button className="btn btn-sm btn-ghost" onClick={() => dupMut.mutate()} title="Duplicate">
            <Copy size={14} />
          </button>
          {canEdit && (
            <button
              className={`btn btn-sm ${editing ? 'btn-success' : 'btn-ghost'}`}
              onClick={() => {
                if (editing) {
                  updateMut.mutate(draft)
                } else {
                  setDraft({})
                  setEditing(true)
                }
              }}
              title="Edit"
            >
              {editing ? (updateMut.isPending ? <span className="loading loading-spinner loading-xs" /> : <Save size={14} />) : <FileText size={14} />}
            </button>
          )}
          {canEdit && (
            <button
              className="btn btn-sm btn-ghost text-error"
              onClick={() => {
                if (confirm('Delete this resource?')) delMut.mutate()
              }}
              title="Delete"
            >
              <Trash2 size={14} />
            </button>
          )}
        </div>
      </div>

      {/* Tags */}
      {resource.tags?.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {resource.tags.map(t => <span key={t} className="badge badge-xs badge-ghost">#{t}</span>)}
        </div>
      )}

      {/* Metadata row */}
      <div className="flex items-center gap-4 text-xs text-base-content/40 font-mono">
        {resource.language && <span>{resource.language}</span>}
        {resource.project && <span>📁 {resource.project}</span>}
        {resource.owner && <span>👤 {resource.owner}</span>}
        <span className="flex items-center gap-1"><Clock size={10} />{new Date(resource.updated_at).toLocaleString()}</span>
        {resource.use_count > 0 && <span>🔗 {resource.use_count} uses</span>}
      </div>

      {/* Tabs */}
      <div className="tabs tabs-boxed tabs-sm">
        {tabs.map(t => {
          const Icon = t.icon
          return (
            <button
              key={t.id}
              className={`tab gap-1 ${tab === t.id ? 'tab-active' : ''}`}
              onClick={() => setTab(t.id)}
            >
              <Icon size={12} /> {t.label}
              {t.id === 'suggestions' && suggestions.length > 0 && (
                <span className="badge badge-xs badge-warning ml-1">{suggestions.length}</span>
              )}
              {t.id === 'versions' && versions.length > 0 && (
                <span className="badge badge-xs badge-ghost ml-1">{versions.length}</span>
              )}
            </button>
          )
        })}
      </div>

      {/* Tab content */}
      <div className="min-h-[300px]">
        {tab === 'preview' && <ResourcePreview resource={resource} />}

        {tab === 'content' && (
          <div className="space-y-2">
            {editing ? (
              <>
                <textarea
                  className="textarea textarea-bordered w-full font-mono text-xs"
                  rows={20}
                  value={draft.content ?? resource.content ?? ''}
                  onChange={(e) => setDraft({ ...draft, content: e.target.value })}
                />
                <div className="flex gap-2">
                  <input
                    className="input input-xs input-bordered flex-1"
                    placeholder="Change note (for version)…"
                    value={(draft as any).change_note ?? ''}
                    onChange={(e) => setDraft({ ...draft, change_note: e.target.value } as any)}
                  />
                  <button className="btn btn-xs btn-success" onClick={() => updateMut.mutate(draft)}>
                    Save
                  </button>
                  <button className="btn btn-xs btn-ghost" onClick={() => { setEditing(false); setDraft({}) }}>
                    Cancel
                  </button>
                </div>
              </>
            ) : (
              <>
                {resource.content ? (
                  <pre className="bg-base-300/50 p-3 rounded-lg font-mono text-xs overflow-x-auto max-h-[500px]">
                    {resource.content}
                  </pre>
                ) : (
                  <p className="text-sm text-base-content/40 text-center py-8">
                    {isRuntime ? 'Runtime resource — content not stored in library' : 'No content'}
                  </p>
                )}
                {canEdit && (
                  <button className="btn btn-xs btn-ghost gap-1" onClick={() => versionMut.mutate('Manual snapshot')}>
                    <GitBranch size={12} /> Snapshot version
                  </button>
                )}
              </>
            )}
          </div>
        )}

        {tab === 'relations' && <RelationPanel resource={resource} />}

        {tab === 'versions' && (
          <div className="space-y-2">
            {canEdit && (
              <button
                className="btn btn-xs btn-ghost gap-1"
                onClick={() => versionMut.mutate(prompt('Change note:') ?? 'Manual snapshot')}
              >
                <GitBranch size={12} /> Create snapshot
              </button>
            )}
            {versions.length === 0 ? (
              <p className="text-sm text-base-content/40 text-center py-8">No versions yet</p>
            ) : (
              versions.map(v => (
                <div key={v.id} className="flex items-center gap-3 px-3 py-2 rounded-lg bg-base-200 group">
                  <GitBranch size={14} className="text-base-content/40" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium">v{v.version}</p>
                    {v.change_note && <p className="text-xs text-base-content/50 truncate">{v.change_note}</p>}
                  </div>
                  <span className="text-[10px] text-base-content/40 font-mono">
                    {new Date(v.created_at).toLocaleString()}
                  </span>
                  {canEdit && (
                    <button
                      className="btn btn-xs btn-ghost text-success opacity-0 group-hover:opacity-100 gap-1"
                      onClick={() => {
                        if (confirm(`Restore to v${v.version}?`)) restoreMut.mutate(v.id)
                      }}
                    >
                      <RotateCcw size={10} /> Restore
                    </button>
                  )}
                </div>
              ))
            )}
          </div>
        )}

        {tab === 'suggestions' && (
          <div className="space-y-2">
            {suggestions.length === 0 ? (
              <p className="text-sm text-base-content/40 text-center py-8">
                <Lightbulb size={20} className="inline mb-1 text-base-content/20" />
                <br />No suggestions — resource looks complete!
              </p>
            ) : (
              suggestions.map((s, i) => (
                <div key={i} className="flex items-center gap-3 px-3 py-2 rounded-lg bg-warning/5 border border-warning/10">
                  <Sparkles size={14} className="text-warning shrink-0" />
                  <div className="flex-1">
                    <p className="text-sm">{s.description}</p>
                    <span className="badge badge-xs badge-ghost">{s.type}</span>
                  </div>
                  {s.type === 'relation' && s.target_id && (
                    <button
                      className="btn btn-xs btn-success"
                      onClick={() => {
                        import('../../api/library').then(m => {
                          m.createRelation(resourceId, { target_id: s.target_id!, relation_type: s.relation_type! })
                          qc.invalidateQueries({ queryKey: ['library-relations', resourceId] })
                          qc.invalidateQueries({ queryKey: ['library-suggestions', resourceId] })
                        })
                      }}
                    >
                      Apply
                    </button>
                  )}
                </div>
              ))
            )}
          </div>
        )}
      </div>
    </div>
  )
}
