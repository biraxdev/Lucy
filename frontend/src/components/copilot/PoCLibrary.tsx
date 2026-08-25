import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Search, Loader2, Play, BookOpen, ChevronRight, AlertCircle } from 'lucide-react'
import { importPoc, getPoc } from '../../api/tasks'
import { listResources } from '../../api/library'
import { getCopilotContext } from '../../api/copilot'
import { useCopilotStore } from '../../stores/copilotStore'
import type { Resource } from '../../types/library'

export function PoCLibrary() {
  const [search, setSearch] = useState('')
  const [selectedPoc, setSelectedPoc] = useState<string | null>(null)
  const [executing, setExecuting] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [pocDetails, setPocDetails] = useState<Record<string, any>>({})
  const queryClient = useQueryClient()
  const { openWithMessage } = useCopilotStore()

  // Use library API with type=poc filter
  const { data: libData, isLoading } = useQuery({
    queryKey: ['pocs-copilot', search],
    queryFn: () => listResources({ q: search, type: ['poc'], limit: 100, sort: 'name' }),
  })

  const pocs: Resource[] = libData?.results ?? []

  const { data: context } = useQuery({
    queryKey: ['copilot-context'],
    queryFn: getCopilotContext,
    refetchInterval: 15000,
  })

  const agents = context?.agents || []
  const onlineAgents = agents.filter((a) => a.status === 'online')

  const handleExpand = async (poc: Resource) => {
    const pocId = poc.source_id ?? poc.name
    if (pocDetails[pocId]) {
      setSelectedPoc(selectedPoc === pocId ? null : pocId)
      return
    }
    try {
      // Fetch full PoC details from the original /pocs/{id} endpoint for step data
      const detail = await getPoc(pocId)
      setPocDetails(prev => ({ ...prev, [pocId]: detail }))
      setSelectedPoc(pocId)
    } catch {
      // Fallback: use library resource metadata
      setPocDetails(prev => ({ ...prev, [pocId]: { steps: poc.metadata?.steps ?? [], category: poc.metadata?.category, mitre: poc.metadata?.mitre } }))
      setSelectedPoc(pocId)
    }
  }

  const handleImport = async (poc: Resource) => {
    const pocId = poc.source_id ?? poc.name
    setExecuting(pocId)
    setError(null)
    try {
      const tl = await importPoc(pocId)
      queryClient.invalidateQueries({ queryKey: ['timelines'] })
      openWithMessage(`J'ai importé le PoC "${poc.name}" en timeline. Veux-tu que je l'exécute contre un agent ?`)
    } catch (e: any) {
      setError(`Import échoué: ${e.message}`)
    } finally {
      setExecuting(null)
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 size={20} className="animate-spin text-success" />
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full min-h-0">
      {/* Search */}
      <div className="shrink-0 p-2 border-b border-base-300 space-y-2">
        <div className="flex items-center gap-1.5 input input-sm input-bordered bg-base-200">
          <Search size={12} className="text-base-content/40" />
          <input
            type="text"
            className="flex-1 bg-transparent outline-none text-xs"
            placeholder="Rechercher un PoC..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <div className="text-[10px] text-base-content/40">
          {pocs.length} PoC · {onlineAgents.length} agents disponibles
        </div>
      </div>

      {error && (
        <div className="shrink-0 px-2 py-1.5 bg-error/10 text-error text-[10px] flex items-center gap-1">
          <AlertCircle size={10} /> {error}
        </div>
      )}

      {/* PoC list */}
      <div className="flex-1 overflow-y-auto p-2 space-y-1.5 min-h-0 scrollbar-thin">
        {pocs.map((poc: Resource) => {
          const pocId = poc.source_id ?? poc.name
          const detail = pocDetails[pocId]
          const steps = detail?.steps || poc.metadata?.steps || []
          const expanded = selectedPoc === pocId
          return (
            <div key={poc.id ?? pocId} className="rounded-lg bg-base-300/50 hover:bg-base-300 transition-colors">
              <div
                className="p-2 cursor-pointer"
                onClick={() => handleExpand(poc)}
              >
                <div className="flex items-center gap-2">
                  <BookOpen size={12} className="text-success shrink-0" />
                  <span className="text-xs font-medium flex-1 truncate">{poc.name}</span>
                  <ChevronRight
                    size={12}
                    className={`text-base-content/40 transition-transform ${expanded ? 'rotate-90' : ''}`}
                  />
                </div>
                {poc.description && (
                  <div className="text-[10px] text-base-content/40 truncate mt-0.5 ml-4">
                    {poc.description}
                  </div>
                )}
                <div className="flex gap-1.5 mt-1 ml-4">
                  {steps.length > 0 && <span className="badge badge-xs badge-ghost">{steps.length} steps</span>}
                  {(detail?.category || poc.metadata?.category) && <span className="badge badge-xs badge-ghost">{detail?.category || poc.metadata?.category}</span>}
                  {(detail?.mitre || poc.metadata?.mitre) && <span className="badge badge-xs badge-info">{detail?.mitre || poc.metadata?.mitre}</span>}
                  {poc.tags?.length > 0 && poc.tags.slice(0, 2).map(t => <span key={t} className="badge badge-xs badge-ghost">#{t}</span>)}
                </div>
              </div>

              {/* Expanded view */}
              {expanded && (
                <div className="px-2 pb-2 space-y-1.5 border-t border-base-300/50 pt-2">
                  {/* Steps preview */}
                  {steps.length > 0 && (
                    <div className="space-y-0.5 max-h-32 overflow-y-auto scrollbar-thin">
                      {steps.slice(0, 10).map((s: any, i: number) => (
                        <div key={i} className="text-[10px] font-mono text-base-content/50 flex gap-1">
                          <span className="text-base-content/30">{i + 1}.</span>
                          <span className="truncate">{s.module}/{s.action}</span>
                        </div>
                      ))}
                      {steps.length > 10 && (
                        <div className="text-[10px] text-base-content/30">+{steps.length - 10} more...</div>
                      )}
                    </div>
                  )}

                  {/* Actions */}
                  <div className="flex gap-1.5">
                    <button
                      className="btn btn-xs btn-outline gap-1 flex-1"
                      onClick={() => handleImport(poc)}
                      disabled={executing === pocId}
                    >
                      {executing === pocId ? (
                        <Loader2 size={10} className="animate-spin" />
                      ) : (
                        <Play size={10} />
                      )}
                      Importer
                    </button>
                    <button
                      className="btn btn-xs btn-success gap-1 flex-1"
                      onClick={() => openWithMessage(`Exécute le PoC "${poc.name}" (${pocId}) contre l'agent FBOX`)}
                    >
                      <Play size={10} /> Via Copilot
                    </button>
                  </div>
                </div>
              )}
            </div>
          )
        })}
        {pocs.length === 0 && (
          <div className="text-center text-base-content/30 py-8 text-xs">
            <BookOpen size={24} className="mx-auto opacity-30 mb-2" />
            Aucun PoC trouvé
          </div>
        )}
      </div>
    </div>
  )
}
