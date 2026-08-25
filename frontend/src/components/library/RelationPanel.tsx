/** RelationPanel — shows outgoing/incoming/auto-suggested relations. */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getRelations, createRelation, deleteRelation } from '../../api/library'
import { Link2, Plus, Trash2, ArrowRight, ArrowLeft, Sparkles } from 'lucide-react'
import { useState } from 'react'
import type { Resource, RelationType } from '../../types/library'

interface Props {
  resource: Resource
}

const RELATION_TYPES: RelationType[] = [
  'related_to', 'references', 'depends_on', 'implements',
  'tests', 'describes', 'affects', 'derived_from', 'part_of', 'replaces',
]

export default function RelationPanel({ resource }: Props) {
  const qc = useQueryClient()
  const [showAdd, setShowAdd] = useState(false)
  const [targetId, setTargetId] = useState('')
  const [relType, setRelType] = useState<RelationType>('related_to')

  const { data: rels, isLoading } = useQuery({
    queryKey: ['library-relations', resource.id],
    queryFn: () => getRelations(resource.id!),
    enabled: !!resource.id,
  })

  const addMut = useMutation({
    mutationFn: () => createRelation(resource.id!, { target_id: targetId, relation_type: relType }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['library-relations', resource.id] })
      setTargetId('')
      setShowAdd(false)
    },
  })

  const delMut = useMutation({
    mutationFn: (rid: string) => deleteRelation(resource.id!, rid),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['library-relations', resource.id] }),
  })

  if (isLoading) {
    return <div className="flex justify-center py-4"><span className="loading loading-spinner loading-sm text-success" /></div>
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h4 className="text-xs font-semibold uppercase tracking-wide text-base-content/50 flex items-center gap-1">
          <Link2 size={12} /> Relations
        </h4>
        <button className="btn btn-xs btn-ghost gap-1" onClick={() => setShowAdd(!showAdd)}>
          <Plus size={12} /> Add
        </button>
      </div>

      {showAdd && (
        <div className="card bg-base-300/50 p-2 space-y-2">
          <input
            className="input input-xs input-bordered w-full"
            placeholder="Target resource ID…"
            value={targetId}
            onChange={(e) => setTargetId(e.target.value)}
          />
          <div className="flex gap-2">
            <select
              className="select select-xs select-bordered flex-1"
              value={relType}
              onChange={(e) => setRelType(e.target.value as RelationType)}
            >
              {RELATION_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
            </select>
            <button
              className="btn btn-xs btn-success"
              disabled={!targetId || addMut.isPending}
              onClick={() => addMut.mutate()}
            >
              {addMut.isPending ? <span className="loading loading-spinner loading-xs" /> : 'Link'}
            </button>
          </div>
        </div>
      )}

      {/* Outgoing */}
      {rels?.outgoing && rels.outgoing.length > 0 && (
        <div className="space-y-1">
          <span className="text-[10px] text-base-content/40 flex items-center gap-1"><ArrowRight size={10} /> Outgoing</span>
          {rels.outgoing.map(rel => (
            <div key={rel.relation_id} className="flex items-center gap-2 px-2 py-1.5 rounded-lg bg-base-200 group">
              <span className="badge badge-xs badge-success">{rel.relation_type}</span>
              <span className="text-xs truncate flex-1">{rel.target?.name ?? 'Unknown'}</span>
              <span className="text-[10px] text-base-content/40">{rel.target?.resource_type}</span>
              <button
                className="btn btn-xs btn-ghost text-error opacity-0 group-hover:opacity-100"
                onClick={() => delMut.mutate(rel.relation_id)}
              >
                <Trash2 size={10} />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Incoming */}
      {rels?.incoming && rels.incoming.length > 0 && (
        <div className="space-y-1">
          <span className="text-[10px] text-base-content/40 flex items-center gap-1"><ArrowLeft size={10} /> Incoming</span>
          {rels.incoming.map(rel => (
            <div key={rel.relation_id} className="flex items-center gap-2 px-2 py-1.5 rounded-lg bg-base-200 group">
              <span className="badge badge-xs badge-info">{rel.relation_type}</span>
              <span className="text-xs truncate flex-1">{rel.source?.name ?? 'Unknown'}</span>
              <span className="text-[10px] text-base-content/40">{rel.source?.resource_type}</span>
              <button
                className="btn btn-xs btn-ghost text-error opacity-0 group-hover:opacity-100"
                onClick={() => delMut.mutate(rel.relation_id)}
              >
                <Trash2 size={10} />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Auto-suggested */}
      {rels?.auto && rels.auto.length > 0 && (
        <div className="space-y-1">
          <span className="text-[10px] text-base-content/40 flex items-center gap-1">
            <Sparkles size={10} className="text-warning" /> Suggested
          </span>
          {rels.auto.map((s, i) => (
            <div key={i} className="flex items-center gap-2 px-2 py-1.5 rounded-lg bg-warning/5 border border-warning/10">
              <span className="badge badge-xs badge-warning">{s.suggested_relation_type}</span>
              <span className="text-xs truncate flex-1">{s.target_name}</span>
              <span className="text-[10px] text-base-content/40">{s.target_type}</span>
              <button
                className="btn btn-xs btn-ghost text-success"
                onClick={() => {
                  setTargetId(s.target_resource_id)
                  setRelType(s.suggested_relation_type)
                  setShowAdd(true)
                }}
              >
                <Plus size={10} />
              </button>
            </div>
          ))}
        </div>
      )}

      {!rels?.outgoing?.length && !rels?.incoming?.length && !rels?.auto?.length && (
        <p className="text-xs text-base-content/40 text-center py-4">No relations yet</p>
      )}
    </div>
  )
}
