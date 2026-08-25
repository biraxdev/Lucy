/** VersionHistory — version list with Monaco diff viewer. */
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getVersions, restoreVersion } from '../../api/library'
import { GitBranch, RotateCcw, Eye, Code2, Clock } from 'lucide-react'
import Editor from '@monaco-editor/react'

interface Props {
  resourceId: string
  canEdit?: boolean
}

export default function VersionHistory({ resourceId, canEdit = true }: Props) {
  const [selectedVersion, setSelectedVersion] = useState<string | null>(null)
  const [viewMode, setViewMode] = useState<'list' | 'diff'>('list')

  const { data: versions = [], isLoading } = useQuery({
    queryKey: ['library-versions', resourceId],
    queryFn: () => getVersions(resourceId),
  })

  const restoreMut = useMutationRestore(resourceId)

  if (isLoading) {
    return <div className="flex justify-center py-8"><span className="loading loading-spinner loading-sm text-success" /></div>
  }

  if (versions.length === 0) {
    return (
      <div className="text-center py-8">
        <GitBranch size={24} className="inline text-base-content/20 mb-2" />
        <p className="text-sm text-base-content/40">No versions yet</p>
      </div>
    )
  }

  const selected = versions.find(v => v.id === selectedVersion)

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h4 className="text-xs font-semibold uppercase tracking-wide text-base-content/50 flex items-center gap-1">
          <GitBranch size={12} /> {versions.length} version{versions.length !== 1 ? 's' : ''}
        </h4>
        <div className="join">
          <button
            className={`btn btn-xs join-item ${viewMode === 'list' ? 'btn-active' : ''}`}
            onClick={() => setViewMode('list')}
          >
            <Clock size={10} /> List
          </button>
          <button
            className={`btn btn-xs join-item ${viewMode === 'diff' ? 'btn-active' : ''}`}
            onClick={() => setViewMode('diff')}
            disabled={!selectedVersion}
          >
            <Code2 size={10} /> Diff
          </button>
        </div>
      </div>

      {viewMode === 'list' && (
        <div className="space-y-1">
          {versions.map(v => (
            <div
              key={v.id}
              className={`flex items-center gap-3 px-3 py-2 rounded-lg cursor-pointer transition-all group ${
                selectedVersion === v.id ? 'bg-success/10 border border-success/20' : 'bg-base-200 hover:bg-base-300/50'
              }`}
              onClick={() => setSelectedVersion(v.id)}
            >
              <GitBranch size={14} className="text-base-content/40 shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium">v{v.version}</p>
                {v.change_note && <p className="text-xs text-base-content/50 truncate">{v.change_note}</p>}
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <span className="text-[10px] text-base-content/40 font-mono">
                  {new Date(v.created_at).toLocaleString()}
                </span>
                {v.created_by && <span className="text-[10px] text-base-content/40">by {v.created_by}</span>}
                {canEdit && (
                  <button
                    className="btn btn-xs btn-ghost text-success opacity-0 group-hover:opacity-100 gap-1"
                    onClick={(e) => {
                      e.stopPropagation()
                      if (confirm(`Restore to v${v.version}?`)) restoreMut.mutate(v.id)
                    }}
                  >
                    <RotateCcw size={10} /> Restore
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {viewMode === 'diff' && selected && (
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-xs">
            <span className="badge badge-sm badge-ghost">v{selected.version}</span>
            {selected.change_note && <span className="text-base-content/50">{selected.change_note}</span>}
            <span className="text-base-content/40 ml-auto">{new Date(selected.created_at).toLocaleString()}</span>
          </div>
          <div className="border border-base-300 rounded-lg overflow-hidden h-[400px]">
            <Editor
              height="100%"
              defaultLanguage="markdown"
              value={selected.content ?? JSON.stringify(selected.snapshot, null, 2)}
              options={{
                readOnly: true,
                minimap: { enabled: false },
                fontSize: 12,
                lineNumbers: 'on',
                wordWrap: 'on',
                renderWhitespace: 'selection',
              }}
              theme="vs-dark"
            />
          </div>
          {canEdit && (
            <button
              className="btn btn-sm btn-success gap-1"
              onClick={() => {
                if (confirm(`Restore to v${selected.version}?`)) restoreMut.mutate(selected.id)
              }}
            >
              <RotateCcw size={14} /> Restore this version
            </button>
          )}
        </div>
      )}
    </div>
  )
}

// --- Mutation hook ---
import { useMutation, useQueryClient } from '@tanstack/react-query'

function useMutationRestore(resourceId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (vid: string) => restoreVersion(resourceId, vid),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['library-resource', resourceId] })
      qc.invalidateQueries({ queryKey: ['library-versions', resourceId] })
    },
  })
}
