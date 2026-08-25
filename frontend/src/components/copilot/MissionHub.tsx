import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Zap, Radar, Wifi, Camera, Monitor, Keyboard, Video, Eye, Clipboard,
  KeyRound, Globe, Cookie, History, Database, Terminal, Anchor, Power, Layers,
  Crosshair, Network, GitBranch, Map, ShieldAlert, ShieldOff, Ghost, ArrowUpCircle,
  FileSearch, Download, Mail, TerminalSquare, Building, Rocket, MapPin, ListTree,
  Play, ChevronRight, Clock, Server, CheckCircle2, AlertCircle, Loader2,
} from 'lucide-react'
import { MISSIONS, CATEGORIES, MISSION_MAP, type Mission, type MissionCategory } from './missions'
import { getCopilotContext, type CopilotContext } from '../../api/copilot'
import { useCopilotStore } from '../../stores/copilotStore'

const ICONS: Record<string, any> = {
  Zap, Radar, Wifi, Camera, Monitor, Keyboard, Video, Eye, Clipboard,
  KeyRound, Globe, Cookie, History, Database, Terminal, Anchor, Power, Layers,
  Crosshair, Network, GitBranch, Map, ShieldAlert, ShieldOff, Ghost, ArrowUpCircle,
  FileSearch, Download, Mail, TerminalSquare, Building, Rocket, MapPin, ListTree,
}

const DIFFICULTY_STYLES: Record<string, { label: string; class: string }> = {
  quick: { label: 'Rapide', class: 'badge-success' },
  standard: { label: 'Standard', class: 'badge-info' },
  advanced: { label: 'Avancé', class: 'badge-warning' },
}

interface Props {
  onLaunch: (mission: Mission, agentId: string) => void
  runningMissionId?: string | null
  completedMissionIds?: Set<string>
}

export function MissionHub({ onLaunch, runningMissionId, completedMissionIds }: Props) {
  const [activeCategory, setActiveCategory] = useState<MissionCategory | 'all'>('all')
  const [search, setSearch] = useState('')
  const [selectedAgent, setSelectedAgent] = useState<string>('')
  const [pendingApproval, setPendingApproval] = useState<Mission | null>(null)
  const { data: context } = useQuery<CopilotContext>({
    queryKey: ['copilot-context'],
    queryFn: getCopilotContext,
    refetchInterval: 10000,
  })

  const agents = context?.agents || []
  const onlineAgents = agents.filter((a) => a.status === 'online')

  // Auto-select first online agent
  useMemo(() => {
    if (!selectedAgent && onlineAgents.length > 0) {
      setSelectedAgent(onlineAgents[0].id)
    }
  }, [onlineAgents, selectedAgent])

  const filtered = useMemo(() => {
    let list = MISSIONS
    if (activeCategory !== 'all') {
      list = list.filter((m) => m.category === activeCategory)
    }
    if (search.trim()) {
      const q = search.toLowerCase()
      list = list.filter((m) =>
        m.title.toLowerCase().includes(q) ||
        m.description.toLowerCase().includes(q) ||
        m.tags.some((t) => t.includes(q))
      )
    }
    return list
  }, [activeCategory, search])

  // Suggested missions (not yet completed)
  const suggested = useMemo(() => {
    const done = completedMissionIds || new Set()
    if (done.size === 0) {
      // New user — show the essentials
      return ['quick-recon', 'credential-harvest', 'wifi-audit', 'screenshot', 'edr-check']
        .map((id) => MISSION_MAP[id])
        .filter(Boolean)
    }
    // After completions, suggest based on last completed
    const last = Array.from(done).pop()
    const lastMission = MISSION_MAP[last || '']
    if (lastMission?.suggests) {
      return lastMission.suggests.map((id) => MISSION_MAP[id]).filter((m) => m && !done.has(m.id))
    }
    return []
  }, [completedMissionIds])

  const handleLaunch = (mission: Mission) => {
    if (!selectedAgent) return
    if (mission.requiresApproval) {
      setPendingApproval(mission)
    } else {
      onLaunch(mission, selectedAgent)
    }
  }

  const confirmApproval = () => {
    if (pendingApproval && selectedAgent) {
      onLaunch(pendingApproval, selectedAgent)
      setPendingApproval(null)
    }
  }

  return (
    <div className="flex flex-col h-full min-h-0">
      {/* Agent selector + search */}
      <div className="shrink-0 p-2.5 border-b border-base-300 space-y-2">
        {/* Agent picker */}
        <div className="flex items-center gap-2">
          <Server size={14} className="text-base-content/40 shrink-0" />
          <select
            className="select select-sm select-bordered flex-1 bg-base-200 text-xs"
            value={selectedAgent}
            onChange={(e) => setSelectedAgent(e.target.value)}
          >
            {onlineAgents.length === 0 && <option value="">Aucun agent online</option>}
            {onlineAgents.map((a) => (
              <option key={a.id} value={a.id}>
                {a.hostname} ({a.os}) — {a.ip || 'no IP'}
              </option>
            ))}
          </select>
          <span className="badge badge-xs badge-success gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-success animate-pulse" />
            {onlineAgents.length} online
          </span>
        </div>

        {/* Search */}
        <div className="flex items-center gap-1.5 input input-sm input-bordered bg-base-200">
          <Zap size={12} className="text-base-content/40" />
          <input
            type="text"
            className="flex-1 bg-transparent outline-none text-xs"
            placeholder="Rechercher une mission..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </div>

      {/* Suggested missions (only when no filter) */}
      {activeCategory === 'all' && !search && suggested.length > 0 && (
        <div className="shrink-0 px-2.5 py-2 border-b border-base-300">
          <div className="text-[10px] uppercase tracking-wider text-base-content/40 font-semibold mb-1.5">
            Recommandé pour toi
          </div>
          <div className="flex gap-1.5 overflow-x-auto scrollbar-thin pb-1">
            {suggested.map((m) => {
              const Icon = ICONS[m.icon] || Zap
              const isDone = completedMissionIds?.has(m.id)
              return (
                <button
                  key={m.id}
                  onClick={() => handleLaunch(m)}
                  disabled={!selectedAgent || runningMissionId !== undefined}
                  className="shrink-0 flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-success/10 border border-success/20 hover:bg-success/20 transition-colors text-xs"
                >
                  <Icon size={12} className="text-success" />
                  <span className="font-medium text-success-content">{m.title}</span>
                  {isDone && <CheckCircle2 size={10} className="text-success" />}
                </button>
              )
            })}
          </div>
        </div>
      )}

      {/* Category filter */}
      <div className="shrink-0 flex gap-0.5 p-1.5 border-b border-base-300 overflow-x-auto scrollbar-thin">
        <button
          className={`shrink-0 btn btn-xs ${activeCategory === 'all' ? 'btn-success' : 'btn-ghost'}`}
          onClick={() => setActiveCategory('all')}
        >
          Toutes ({MISSIONS.length})
        </button>
        {CATEGORIES.map((cat) => {
          const count = MISSIONS.filter((m) => m.category === cat.id).length
          if (count === 0) return null
          return (
            <button
              key={cat.id}
              className={`shrink-0 btn btn-xs gap-1 ${activeCategory === cat.id ? 'btn-success' : 'btn-ghost'}`}
              onClick={() => setActiveCategory(cat.id)}
            >
              {cat.label} ({count})
            </button>
          )
        })}
      </div>

      {/* Mission cards */}
      <div className="flex-1 overflow-y-auto p-2 space-y-1.5 min-h-0 scrollbar-thin">
        <AnimatePresence mode="popLayout">
          {filtered.map((mission) => {
            const Icon = ICONS[mission.icon] || Zap
            const diff = DIFFICULTY_STYLES[mission.difficulty]
            const isRunning = runningMissionId === mission.id
            const isDone = completedMissionIds?.has(mission.id)
            const canRun = selectedAgent && !isRunning

            return (
              <motion.div
                key={mission.id}
                layout
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.95 }}
                transition={{ duration: 0.15 }}
                className={`rounded-xl border transition-all ${
                  isRunning
                    ? 'border-success/40 bg-success/5 shadow-[0_0_12px_rgba(0,255,157,0.1)]'
                    : isDone
                      ? 'border-success/20 bg-success/5'
                      : 'border-base-300/50 bg-base-300/30 hover:border-base-300 hover:bg-base-300/50'
                }`}
              >
                <div className="p-2.5">
                  {/* Header */}
                  <div className="flex items-start gap-2.5">
                    <div className={`shrink-0 w-9 h-9 rounded-lg flex items-center justify-center ${
                      isRunning ? 'bg-success/20 text-success' : 'bg-base-300/50 text-base-content/60'
                    }`}>
                      {isRunning ? (
                        <Loader2 size={16} className="animate-spin" />
                      ) : (
                        <Icon size={16} />
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-1.5">
                        <h3 className="text-sm font-semibold truncate">{mission.title}</h3>
                        {isDone && <CheckCircle2 size={12} className="text-success shrink-0" />}
                      </div>
                      <p className="text-[11px] text-base-content/50 leading-tight mt-0.5 line-clamp-2">
                        {mission.description}
                      </p>
                    </div>
                  </div>

                  {/* Meta */}
                  <div className="flex items-center gap-1.5 mt-2 flex-wrap">
                    <span className={`badge badge-xs ${diff.class}`}>{diff.label}</span>
                    <span className="badge badge-xs badge-ghost gap-0.5">
                      <Clock size={8} /> {mission.duration}
                    </span>
                    <span className="badge badge-xs badge-ghost">
                      {mission.steps.length} étapes
                    </span>
                    {mission.multiAgent && (
                      <span className="badge badge-xs badge-ghost">multi-agent</span>
                    )}
                    {mission.mitre && mission.mitre.length > 0 && (
                      <span className="badge badge-xs badge-ghost opacity-50">
                        MITRE: {mission.mitre.length}
                      </span>
                    )}
                  </div>

                  {/* Steps preview */}
                  <div className="mt-2 space-y-0.5">
                    {mission.steps.slice(0, 4).map((step, i) => (
                      <div key={i} className="flex items-center gap-1.5 text-[10px] text-base-content/40">
                        <span className="w-3.5 h-3.5 rounded-full bg-base-300/50 flex items-center justify-center text-[8px] font-mono shrink-0">
                          {i + 1}
                        </span>
                        <span className="font-mono truncate">{step.module}/{step.action}</span>
                        <span className="text-base-content/30 truncate">— {step.label}</span>
                      </div>
                    ))}
                    {mission.steps.length > 4 && (
                      <div className="text-[10px] text-base-content/30 ml-5">
                        +{mission.steps.length - 4} étapes...
                      </div>
                    )}
                  </div>

                  {/* Actions */}
                  <div className="flex gap-1.5 mt-2.5">
                    <button
                      className={`btn btn-sm flex-1 gap-1 ${
                        isRunning ? 'btn-disabled' : canRun ? 'btn-success' : 'btn-outline btn-disabled'
                      }`}
                      onClick={() => handleLaunch(mission)}
                      disabled={!canRun}
                    >
                      {isRunning ? (
                        <><Loader2 size={12} className="animate-spin" /> En cours...</>
                      ) : isDone ? (
                        <><Play size={12} /> Relancer</>
                      ) : (
                        <><Play size={12} /> Lancer</>
                      )}
                    </button>
                    {mission.suggests && mission.suggests.length > 0 && (
                      <div className="hidden group relative">
                        <button className="btn btn-sm btn-ghost btn-square">
                          <ChevronRight size={14} />
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              </motion.div>
            )
          })}
        </AnimatePresence>

        {filtered.length === 0 && (
          <div className="text-center text-base-content/30 py-8 text-xs">
            Aucune mission trouvée
          </div>
        )}
      </div>

      {/* No agent warning */}
      {onlineAgents.length === 0 && (
        <div className="shrink-0 p-2.5 border-t border-base-300 bg-error/5">
          <div className="flex items-center gap-2 text-xs text-error">
            <AlertCircle size={14} />
            <span>Aucun agent connecté. Lance un agent FBOX pour commencer.</span>
          </div>
        </div>
      )}

      {/* Approval modal for destructive missions */}
      <AnimatePresence>
        {pendingApproval && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[200] flex items-center justify-center bg-black/60 p-4"
            onClick={() => setPendingApproval(null)}
          >
            <motion.div
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.9, opacity: 0 }}
              className="bg-base-100 rounded-2xl border border-error/30 shadow-2xl max-w-sm w-full p-4 space-y-3"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-center gap-2 text-error">
                <AlertCircle size={20} />
                <h3 className="text-sm font-bold">Confirmation requise</h3>
              </div>
              <p className="text-xs text-base-content/70">
                La mission <strong className="text-error">{pendingApproval.title}</strong> est une opération
                à impact élevé qui modifie le système cible.
              </p>
              <div className="bg-error/10 rounded-lg p-2 text-[10px] text-error/80 space-y-0.5">
                {pendingApproval.steps.map((s, i) => (
                  <div key={i} className="font-mono">• {s.module}/{s.action} — {s.label}</div>
                ))}
              </div>
              <p className="text-[10px] text-base-content/40">
                Cette action sera auditée et loggée. Assure-toi d'avoir l'autorisation d'effectuer cette opération.
              </p>
              <div className="flex gap-2">
                <button
                  className="btn btn-sm btn-ghost flex-1"
                  onClick={() => setPendingApproval(null)}
                >
                  Annuler
                </button>
                <button
                  className="btn btn-sm btn-error flex-1 gap-1"
                  onClick={confirmApproval}
                >
                  <Play size={12} /> Confirmer & Lancer
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
