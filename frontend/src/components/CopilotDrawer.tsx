import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Brain, Globe, Server, BookOpen, X, Rocket, Home,
} from 'lucide-react'
import { useLocation } from 'react-router-dom'
import { useCopilotStore } from '../stores/copilotStore'
import { MissionHub } from './copilot/MissionHub'
import { MissionRunner } from './copilot/MissionRunner'
import { ChatPanel } from './copilot/ChatPanel'
import { WebBrowser } from './copilot/WebBrowser'
import { LucyExplorer } from './copilot/LucyExplorer'
import { PoCLibrary } from './copilot/PoCLibrary'
import { MISSION_MAP, type Mission } from './copilot/missions'

type CopilotView =
  | { kind: 'home' }
  | { kind: 'mission'; mission: Mission; agentId: string }
  | { kind: 'chat' }
  | { kind: 'web' }
  | { kind: 'explorer' }
  | { kind: 'poc' }

const tabs = [
  { id: 'home' as const, label: 'Missions', icon: Rocket },
  { id: 'chat' as const, label: 'Chat', icon: Brain },
  { id: 'web' as const, label: 'Web', icon: Globe },
  { id: 'explorer' as const, label: 'Lucy', icon: Server },
  { id: 'poc' as const, label: 'PoC', icon: BookOpen },
]

export function CopilotDrawer() {
  const { open, setOpen, setContextPage, prefillMessage, setPrefill } = useCopilotStore()
  const location = useLocation()
  const [activeTab, setActiveTab] = useState<'home' | 'chat' | 'web' | 'explorer' | 'poc'>('home')
  const [view, setView] = useState<CopilotView>({ kind: 'home' })
  const [completedMissions, setCompletedMissions] = useState<Set<string>>(new Set())

  // Update context page when route changes
  useEffect(() => {
    const path = location.pathname.replace(/^\//, '') || 'dashboard'
    setContextPage(path)
  }, [location.pathname, setContextPage])

  // ESC to close
  useEffect(() => {
    if (!open) return
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false)
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [open, setOpen])

  // Handle prefill — switch to chat tab
  useEffect(() => {
    if (prefillMessage) {
      setActiveTab('chat')
      setView({ kind: 'chat' })
    }
  }, [prefillMessage, setPrefill])

  const handleLaunchMission = (mission: Mission, agentId: string) => {
    setView({ kind: 'mission', mission, agentId })
  }

  const handleMissionBack = () => {
    setView({ kind: 'home' })
    setActiveTab('home')
  }

  const handleMissionComplete = (missionId: string) => {
    setCompletedMissions((prev) => new Set(prev).add(missionId))
  }

  const handleTabChange = (tab: typeof activeTab) => {
    setActiveTab(tab)
    setView({ kind: tab })
  }

  const isMissionView = view.kind === 'mission'

  return (
    <AnimatePresence>
      {open && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/30 z-[140] lg:bg-transparent"
            onClick={() => setOpen(false)}
          />

          {/* Drawer */}
          <motion.div
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'spring', stiffness: 300, damping: 30 }}
            className="fixed right-0 top-0 bottom-0 z-[145] w-full sm:w-[440px] lg:w-[500px]
                       bg-base-100 border-l border-base-300 shadow-2xl flex flex-col"
          >
            {/* Header */}
            <div className="shrink-0 flex items-center justify-between px-3 py-2.5 border-b border-base-300 bg-base-200/50">
              <div className="flex items-center gap-2">
                {isMissionView ? (
                  <button
                    className="btn btn-sm btn-ghost btn-square"
                    onClick={handleMissionBack}
                  >
                    <Home size={14} />
                  </button>
                ) : (
                  <div className="relative">
                    <Rocket size={18} className="text-success" />
                    <div className="absolute inset-0 rounded-full bg-success/20 animate-ping" />
                  </div>
                )}
                <div>
                  <div className="text-sm font-bold">
                    {isMissionView ? (view as any).mission.title : 'Lucy Copilot'}
                  </div>
                  <div className="text-[9px] text-base-content/40 uppercase tracking-wider">
                    {isMissionView ? 'Mission en cours' : 'AI Operations Center'}
                  </div>
                </div>
              </div>
              <button
                className="btn btn-sm btn-ghost btn-square"
                onClick={() => setOpen(false)}
              >
                <X size={16} />
              </button>
            </div>

            {/* Tabs (hidden during mission execution) */}
            {!isMissionView && (
              <div className="shrink-0 flex gap-0.5 p-1.5 border-b border-base-300 bg-base-200/30">
                {tabs.map((tab) => (
                  <button
                    key={tab.id}
                    className={`flex-1 flex flex-col items-center gap-0.5 py-1.5 rounded-lg transition-all ${
                      activeTab === tab.id
                        ? 'bg-success/10 text-success'
                        : 'text-base-content/40 hover:text-base-content/70 hover:bg-base-300/50'
                    }`}
                    onClick={() => handleTabChange(tab.id)}
                  >
                    <tab.icon size={16} />
                    <span className="text-[10px] font-medium">{tab.label}</span>
                  </button>
                ))}
              </div>
            )}

            {/* Content */}
            <div className="flex-1 min-h-0 overflow-hidden">
              <AnimatePresence mode="wait">
                {view.kind === 'home' && (
                  <motion.div
                    key="home"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    className="h-full"
                  >
                    <MissionHub
                      onLaunch={handleLaunchMission}
                      runningMissionId={null}
                      completedMissionIds={completedMissions}
                    />
                  </motion.div>
                )}

                {view.kind === 'mission' && (
                  <motion.div
                    key="mission"
                    initial={{ opacity: 0, x: 20 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: 20 }}
                    className="h-full"
                    onAnimationComplete={() => {
                      // Mark complete when runner unmounts after done
                    }}
                  >
                    <MissionRunner
                      mission={view.mission}
                      agentId={view.agentId}
                      onBack={handleMissionBack}
                      onChatAsk={(q) => {
                        setPrefill(q)
                        setActiveTab('chat')
                        setView({ kind: 'chat' })
                      }}
                    />
                  </motion.div>
                )}

                {view.kind === 'chat' && (
                  <motion.div
                    key="chat"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    className="h-full"
                  >
                    <ChatPanel />
                  </motion.div>
                )}

                {view.kind === 'web' && (
                  <motion.div
                    key="web"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    className="h-full"
                  >
                    <WebBrowser />
                  </motion.div>
                )}

                {view.kind === 'explorer' && (
                  <motion.div
                    key="explorer"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    className="h-full"
                  >
                    <LucyExplorer />
                  </motion.div>
                )}

                {view.kind === 'poc' && (
                  <motion.div
                    key="poc"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    className="h-full"
                  >
                    <PoCLibrary />
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
