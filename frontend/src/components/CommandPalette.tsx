import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Search, CornerDownLeft, ArrowRight, Command,
  LayoutDashboard, MessageCircle, Target, Server, ListTodo, Puzzle,
  GitBranch, Settings, Map, Terminal, Hammer, BarChart2, Wrench, FileText, Bell, Bug, Users, KeyRound, ScrollText, Monitor, Crosshair,
  Zap, Plus, Activity, Download, RefreshCw, Power, ShieldCheck, Network, Sparkles,
} from 'lucide-react'
import { useCopilotStore } from '../stores/copilotStore'
import { executeTimeline } from '../api/tasks'

interface CommandItem {
  id: string
  label: string
  description?: string
  icon: React.ElementType
  category: string
  action: () => void
  keywords?: string[]
}

export function CommandPalette() {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [selectedIndex, setSelectedIndex] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLDivElement>(null)
  const navigate = useNavigate()
  const toggleCopilot = useCopilotStore((s) => s.toggleOpen)

  // Global keybind: Cmd+K / Ctrl+K
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        setOpen(prev => !prev)
      }
      if (e.key === 'Escape') setOpen(false)
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])

  useEffect(() => {
    if (open) {
      setQuery('')
      setSelectedIndex(0)
      setTimeout(() => inputRef.current?.focus(), 50)
    }
  }, [open])

  const go = useCallback((path: string) => {
    navigate(path)
    setOpen(false)
  }, [navigate])

  const commands: CommandItem[] = [
    // Copilot
    { id: 'copilot', label: 'Open AI Copilot', icon: Sparkles, category: 'Copilot', action: () => { toggleCopilot(); setOpen(false) }, description: 'Open the unified AI Copilot drawer (Ctrl+J)', keywords: ['ai', 'chat', 'assistant', 'copilot'] },

    // Navigation
    { id: 'nav-dashboard', label: 'Dashboard', icon: LayoutDashboard, category: 'Navigate', action: () => go('/') },
    { id: 'nav-chat', label: 'Chat with Lucy', icon: MessageCircle, category: 'Navigate', action: () => go('/chat') },
    { id: 'nav-mission', label: 'Mission View', icon: Crosshair, category: 'Navigate', action: () => go('/mission'), description: 'Unified mission overview' },
    { id: 'nav-strategy', label: 'Strategy', icon: Target, category: 'Navigate', action: () => go('/strategy') },
    { id: 'nav-agents', label: 'Agents', icon: Server, category: 'Navigate', action: () => go('/agents') },
    { id: 'nav-tasks', label: 'Tasks', icon: ListTodo, category: 'Navigate', action: () => go('/tasks') },
    { id: 'nav-groups', label: 'Groups', icon: Users, category: 'Navigate', action: () => go('/groups') },
    { id: 'nav-terminal', label: 'Terminal', icon: Terminal, category: 'Navigate', action: () => go('/terminal') },
    { id: 'nav-credentials', label: 'Credentials', icon: KeyRound, category: 'Navigate', action: () => go('/credentials') },
    { id: 'nav-findings', label: 'Findings', icon: Bug, category: 'Navigate', action: () => go('/findings') },
    { id: 'nav-alerts', label: 'Alerts', icon: Bell, category: 'Navigate', action: () => go('/alerts') },
    { id: 'nav-logs', label: 'Logs', icon: ScrollText, category: 'Navigate', action: () => go('/logs') },
    { id: 'nav-reports', label: 'Reports', icon: FileText, category: 'Navigate', action: () => go('/reports') },
    { id: 'nav-builder', label: 'Agent Builder', icon: Hammer, category: 'Navigate', action: () => go('/builder') },
    { id: 'nav-modules', label: 'Module Store', icon: Puzzle, category: 'Navigate', action: () => go('/modules') },
    { id: 'nav-timelines', label: 'Timelines', icon: GitBranch, category: 'Navigate', action: () => go('/timelines') },
    { id: 'nav-gantt', label: 'Gantt View', icon: BarChart2, category: 'Navigate', action: () => go('/gantt') },
    { id: 'nav-map', label: 'Map', icon: Map, category: 'Navigate', action: () => go('/map') },
    { id: 'nav-settings', label: 'Settings', icon: Settings, category: 'Navigate', action: () => go('/settings') },
    { id: 'nav-rbac', label: 'Roles & Access', icon: ShieldCheck, category: 'Navigate', action: () => go('/rbac'), description: 'Manage operator roles and permissions' },
    { id: 'nav-c2profiles', label: 'C2 Profiles', icon: Network, category: 'Navigate', action: () => go('/c2-profiles'), description: 'Malleable C2 traffic profiles' },

    // Quick Actions
    { id: 'act-build', label: 'Build New Agent', icon: Plus, category: 'Action', action: () => go('/builder'), description: 'Create a new agent payload' },
    { id: 'act-recon', label: 'Quick Recon', icon: Zap, category: 'Action', action: () => {
      executeTimeline('recon-default')
      setOpen(false)
    }, description: 'Dispatch default recon timeline' },
    { id: 'act-report', label: 'Generate Report', icon: FileText, category: 'Action', action: () => go('/reports'), description: 'Create engagement report' },
    { id: 'act-terminal', label: 'Broadcast Shell', icon: Terminal, category: 'Action', action: () => go('/terminal'), description: 'Send command to all agents' },
  ]

  const filtered = commands.filter(c => {
    if (!query) return true
    const q = query.toLowerCase()
    return c.label.toLowerCase().includes(q) ||
      c.category.toLowerCase().includes(q) ||
      c.description?.toLowerCase().includes(q) ||
      c.keywords?.some(k => k.includes(q))
  })

  // Group by category
  const grouped = filtered.reduce<Record<string, CommandItem[]>>((acc, c) => {
    acc[c.category] = acc[c.category] || []
    acc[c.category].push(c)
    return acc
  }, {})

  const flatList = Object.entries(grouped).flatMap(([cat, items]) => items)

  useEffect(() => {
    setSelectedIndex(0)
  }, [query])

  useEffect(() => {
    const item = listRef.current?.children[selectedIndex] as HTMLElement
    item?.scrollIntoView({ block: 'nearest' })
  }, [selectedIndex])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setSelectedIndex(i => Math.min(i + 1, flatList.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setSelectedIndex(i => Math.max(i - 1, 0))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      flatList[selectedIndex]?.action()
    }
  }

  let runningIndex = 0

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-[200] flex items-start justify-center pt-[15vh] bg-black/60 backdrop-blur-sm"
          onClick={() => setOpen(false)}
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.96, y: -10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: -10 }}
            transition={{ duration: 0.15 }}
            onClick={e => e.stopPropagation()}
            className="w-full max-w-xl bg-base-100 rounded-2xl shadow-2xl border border-base-300 overflow-hidden"
          >
            {/* Search input */}
            <div className="flex items-center gap-3 px-4 py-3 border-b border-base-300">
              <Search size={18} className="text-base-content/40 shrink-0" />
              <input
                ref={inputRef}
                type="text"
                value={query}
                onChange={e => setQuery(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Search commands, pages, actions…"
                className="flex-1 bg-transparent outline-none text-sm placeholder:text-base-content/30"
              />
              <kbd className="kbd kbd-xs text-[10px]">ESC</kbd>
            </div>

            {/* Results */}
            <div ref={listRef} className="max-h-[50vh] overflow-y-auto scrollbar-thin py-2">
              {Object.entries(grouped).map(([category, items]) => (
                <div key={category}>
                  <div className="px-4 py-1.5 text-[10px] font-bold uppercase tracking-wider text-base-content/30">
                    {category}
                  </div>
                  {items.map((item) => {
                    const idx = runningIndex++
                    const isActive = idx === selectedIndex
                    const Icon = item.icon
                    return (
                      <button
                        key={item.id}
                        onClick={item.action}
                        onMouseEnter={() => setSelectedIndex(idx)}
                        className={`w-full flex items-center gap-3 px-4 py-2.5 text-left transition-colors ${
                          isActive ? 'bg-success/10 text-success' : 'text-base-content/70 hover:bg-base-200'
                        }`}
                      >
                        <Icon size={16} className="shrink-0" />
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium truncate">{item.label}</p>
                          {item.description && <p className="text-[11px] text-base-content/40 truncate">{item.description}</p>}
                        </div>
                        {isActive && <CornerDownLeft size={14} className="text-success shrink-0" />}
                      </button>
                    )
                  })}
                </div>
              ))}
              {flatList.length === 0 && (
                <div className="px-4 py-8 text-center text-base-content/30 text-sm">
                  No results for "{query}"
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="flex items-center justify-between px-4 py-2 border-t border-base-300 bg-base-200/50 text-[10px] text-base-content/40">
              <div className="flex items-center gap-2">
                <Command size={12} />
                <span>Command Palette</span>
              </div>
              <div className="flex items-center gap-2">
                <kbd className="kbd kbd-xs">↑↓</kbd> navigate
                <kbd className="kbd kbd-xs">↵</kbd> select
              </div>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
