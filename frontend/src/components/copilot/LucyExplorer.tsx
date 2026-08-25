import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Server, Activity, Code, GitBranch, KeyRound, Bug,
  ChevronRight, Circle, Search, Loader2, Zap, Send,
} from 'lucide-react'
import { getCopilotContext, dispatchTask, type CopilotContext } from '../../api/copilot'
import { useCopilotStore } from '../../stores/copilotStore'
import { useUIStore } from '../../stores/uiStore'

type Section = 'agents' | 'tasks' | 'modules' | 'credentials' | 'findings'

export function LucyExplorer() {
  const [section, setSection] = useState<Section>('agents')
  const [search, setSearch] = useState('')
  const [dispatching, setDispatching] = useState<string | null>(null)
  const queryClient = useQueryClient()
  const { openWithMessage } = useCopilotStore()
  const { openAgent } = useUIStore()

  const { data: context, isLoading } = useQuery<CopilotContext>({
    queryKey: ['copilot-context'],
    queryFn: getCopilotContext,
    refetchInterval: 10000,
  })

  const sections: Array<{ id: Section; label: string; icon: any; count?: number }> = [
    { id: 'agents', label: 'Agents', icon: Server, count: context?.stats.agents },
    { id: 'tasks', label: 'Tasks', icon: Activity, count: context?.stats.tasks },
    { id: 'modules', label: 'Modules', icon: Code, count: context?.stats.modules },
    { id: 'credentials', label: 'Credentials', icon: KeyRound, count: context?.stats.credentials },
    { id: 'findings', label: 'Findings', icon: Bug, count: context?.stats.findings },
  ]

  const filtered = (items: any[], fields: string[]) => {
    if (!search.trim()) return items
    const q = search.toLowerCase()
    return items.filter((item) =>
      fields.some((f) => String(item[f] ?? '').toLowerCase().includes(q))
    )
  }

  const handleQuickAction = async (agentId: string, agentName: string, action: string) => {
    setDispatching(`${agentId}-${action}`)
    try {
      const moduleMap: Record<string, { module: string; action: string; params: Record<string, unknown> }> = {
        screenshot: { module: 'screenshot', action: 'capture', params: {} },
        info: { module: 'info', action: 'run', params: {} },
        shell: { module: 'shell', action: 'exec', params: { cmd: 'whoami' } },
        wifi: { module: 'wifi', action: 'status', params: {} },
      }
      const config = moduleMap[action]
      if (!config) return
      await dispatchTask({ agent_id: agentId, ...config })
      queryClient.invalidateQueries({ queryKey: ['copilot-context'] })
      openWithMessage(`J'ai envoyé une task ${action} à ${agentName}. Surveille le résultat et dis-moi ce que tu vois.`)
    } finally {
      setDispatching(null)
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
      {/* Section tabs */}
      <div className="shrink-0 flex gap-0.5 p-1.5 border-b border-base-300">
        {sections.map((s) => (
          <button
            key={s.id}
            className={`btn btn-xs gap-1 flex-1 ${section === s.id ? 'btn-success' : 'btn-ghost'}`}
            onClick={() => setSection(s.id)}
          >
            <s.icon size={11} />
            <span className="text-[10px]">{s.label}</span>
            {s.count !== undefined && (
              <span className="badge badge-xs badge-ghost ml-0.5">{s.count}</span>
            )}
          </button>
        ))}
      </div>

      {/* Search */}
      <div className="shrink-0 p-2 border-b border-base-300">
        <div className="flex items-center gap-1.5 input input-sm input-bordered bg-base-200">
          <Search size={12} className="text-base-content/40" />
          <input
            type="text"
            className="flex-1 bg-transparent outline-none text-xs"
            placeholder={`Rechercher dans ${section}...`}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-2 space-y-1 min-h-0 scrollbar-thin">
        {section === 'agents' && (
          <>
            {filtered(context?.agents || [], ['hostname', 'os', 'status', 'ip']).map((a) => (
              <div key={a.id} className="p-2 rounded-lg bg-base-300/50 hover:bg-base-300 transition-colors space-y-1.5">
                <div className="flex items-center gap-2">
                  <Circle
                    size={8}
                    className={a.status === 'online' ? 'fill-success text-success' : 'fill-base-content/20 text-base-content/20'}
                  />
                  <span className="text-xs font-medium flex-1 truncate">{a.hostname}</span>
                  <button
                    className="btn btn-xs btn-ghost btn-square"
                    onClick={() => openAgent(a.id)}
                    title="Détails"
                  >
                    <ChevronRight size={12} />
                  </button>
                </div>
                <div className="text-[10px] text-base-content/40 flex gap-2">
                  <span>{a.os}</span>
                  <span>·</span>
                  <span>{a.ip || '?'}</span>
                  <span>·</span>
                  <span>{a.username}</span>
                </div>
                {/* Quick actions */}
                <div className="flex gap-1">
                  {['screenshot', 'info', 'shell', 'wifi'].map((act) => (
                    <button
                      key={act}
                      className="badge badge-xs badge-ghost cursor-pointer hover:badge-success text-[9px] gap-0.5"
                      onClick={() => handleQuickAction(a.id, a.hostname, act)}
                      disabled={dispatching === `${a.id}-${act}`}
                    >
                      {dispatching === `${a.id}-${act}` ? (
                        <Loader2 size={8} className="animate-spin" />
                      ) : act === 'screenshot' ? (
                        <Zap size={8} />
                      ) : (
                        <Send size={8} />
                      )}
                      {act}
                    </button>
                  ))}
                </div>
              </div>
            ))}
            {(context?.agents || []).length === 0 && (
              <div className="text-center text-base-content/30 py-4 text-xs">Aucun agent</div>
            )}
          </>
        )}

        {section === 'tasks' && (
          <>
            {filtered(context?.recent_tasks || [], ['module', 'action', 'status']).map((t) => (
              <div key={t.id} className="p-2 rounded-lg bg-base-300/50 flex items-center gap-2">
                <Circle
                  size={8}
                  className={
                    t.status === 'completed' ? 'fill-success text-success' :
                    t.status === 'failed' ? 'fill-error text-error' :
                    t.status === 'running' ? 'fill-info text-info animate-pulse' :
                    'fill-base-content/20 text-base-content/20'
                  }
                />
                <div className="flex-1 min-w-0">
                  <div className="text-xs font-mono truncate">{t.module}/{t.action}</div>
                  <div className="text-[10px] text-base-content/40">{t.status}</div>
                </div>
              </div>
            ))}
            {(context?.recent_tasks || []).length === 0 && (
              <div className="text-center text-base-content/30 py-4 text-xs">Aucune tâche récente</div>
            )}
          </>
        )}

        {section === 'modules' && (
          <>
            {filtered(context?.modules || [], ['name', 'category', 'description']).map((m) => (
              <div key={m.id} className="p-2 rounded-lg bg-base-300/50">
                <div className="text-xs font-mono font-medium">{m.name}</div>
                <div className="text-[10px] text-base-content/40">{m.category}</div>
                {m.description && (
                  <div className="text-[10px] text-base-content/30 truncate mt-0.5">{m.description}</div>
                )}
              </div>
            ))}
            {(context?.modules || []).length === 0 && (
              <div className="text-center text-base-content/30 py-4 text-xs">Aucun module</div>
            )}
          </>
        )}

        {section === 'credentials' && (
          <div className="text-center text-base-content/30 py-8 text-xs space-y-2">
            <KeyRound size={24} className="mx-auto opacity-30" />
            <p>{context?.stats.credentials || 0} credentials stockés</p>
            <button
              className="btn btn-xs btn-outline"
              onClick={() => openWithMessage('Liste tous les credentials stockés dans Lucy')}
            >
              Demander au Copilot
            </button>
          </div>
        )}

        {section === 'findings' && (
          <div className="text-center text-base-content/30 py-8 text-xs space-y-2">
            <Bug size={24} className="mx-auto opacity-30" />
            <p>{context?.stats.findings || 0} findings</p>
            <button
              className="btn btn-xs btn-outline"
              onClick={() => openWithMessage('Analyse les findings et suggère des prochaines étapes')}
            >
              Analyser avec Copilot
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
