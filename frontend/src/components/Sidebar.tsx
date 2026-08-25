import { NavLink, useLocation } from 'react-router-dom'
import {
  Server, MessageCircle, Hammer, Settings,
  ShieldAlert, Shield, Workflow, Brain, Zap, LayoutDashboard,
  ChevronRight, FolderCode, Radio, Map, BarChart3, Users, FileText, Bell,
  KeyRound, Globe, Crosshair, Terminal, Sparkles, Library as LibraryIcon, Package,
} from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { useUIStore } from '../stores/uiStore'
import { useCopilotStore } from '../stores/copilotStore'
import { useState } from 'react'

type LinkItem = {
  to: string
  icon: React.ElementType
  label: string
  badge?: string
}

type Section = {
  title: string
  items: LinkItem[]
}

const sections: Section[] = [
  {
    title: 'Mission',
    items: [
      { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
      { to: '/agents', icon: Server, label: 'Endpoints' },
      { to: '/map', icon: Map, label: 'Map' },
      { to: '/defense', icon: Shield, label: 'Defense Center' },
    ],
  },
  {
    title: 'Operations',
    items: [
      { to: '/tasks', icon: Crosshair, label: 'Tasks' },
      { to: '/builder', icon: Hammer, label: 'Agent Builder' },
      { to: '/packs', icon: Package, label: 'Packs' },
      { to: '/script-builder', icon: Workflow, label: 'Script Builder' },
      { to: '/chat', icon: MessageCircle, label: 'Operator Chat' },
    ],
  },
  {
    title: 'Intelligence',
    items: [
      { to: '/library', icon: LibraryIcon, label: 'Library' },
      { to: '/ai-agent', icon: Brain, label: 'AI Planner' },
    ],
  },
  {
    title: 'Data',
    items: [
      { to: '/findings', icon: FileText, label: 'Findings' },
      { to: '/credentials', icon: KeyRound, label: 'Credentials' },
      { to: '/alerts', icon: Bell, label: 'Alerts' },
      { to: '/logs', icon: Terminal, label: 'Logs' },
    ],
  },
  {
    title: 'System',
    items: [
      { to: '/settings', icon: Settings, label: 'Settings' },
    ],
  },
]

function NavItem({ item, isOpen, isActive }: { item: LinkItem; isOpen: boolean; isActive: boolean }) {
  const Icon = item.icon
  return (
    <NavLink
      to={item.to}
      className={({ isActive }) =>
        `group relative flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-200 overflow-hidden
         ${isActive
           ? 'bg-success/10 text-success shadow-[0_0_12px_rgba(0,255,157,0.08)]'
           : 'text-base-content/50 hover:text-base-content/80 hover:bg-base-300/50'
        }`
      }
    >
      {/* Active glow indicator */}
      {isActive && (
        <motion.div
          layoutId="sidebar-active"
          className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-6 rounded-full bg-success shadow-[0_0_8px_rgba(0,255,157,0.5)]"
          transition={{ type: 'spring', stiffness: 300, damping: 30 }}
        />
      )}

      <div className={`
        relative flex items-center justify-center w-8 h-8 rounded-lg transition-all duration-200 shrink-0
        ${isActive ? 'bg-success/15 text-success' : 'bg-base-300/30 text-base-content/40 group-hover:text-base-content/60 group-hover:bg-base-300/50'}
      `}>
        <Icon size={16} strokeWidth={1.5} />
        {isActive && (
          <div className="absolute inset-0 rounded-lg bg-success/10 animate-pulse-glow" />
        )}
      </div>

      {isOpen && (
        <motion.span
          initial={{ opacity: 0, x: -8 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.2 }}
          className="truncate"
        >
          {item.label}
        </motion.span>
      )}

      {isActive && isOpen && (
        <ChevronRight size={14} className="ml-auto text-success/50 opacity-0 group-hover:opacity-100 transition-opacity" />
      )}
    </NavLink>
  )
}

function SectionHeader({ title, isOpen }: { title: string; isOpen: boolean }) {
  if (!isOpen) return null
  return (
    <div className="px-3 pt-4 pb-1">
      <p className="text-[10px] font-semibold uppercase tracking-[0.15em] text-base-content/25">
        {title}
      </p>
    </div>
  )
}

export default function Sidebar() {
  const open = useUIStore((s) => s.sidebarOpen)
  const location = useLocation()
  const copilotOpen = useCopilotStore((s) => s.open)
  const toggleCopilot = useCopilotStore((s) => s.toggleOpen)

  return (
    <aside
      className={`flex flex-col bg-base-200/80 backdrop-blur-xl border-r border-white/[0.03] transition-all duration-300 ease-out ${open ? 'w-64' : 'w-[4.5rem]'} shrink-0 h-screen sticky top-0 z-30`}
    >
      {/* Logo */}
      <div className="flex items-center gap-3 px-4 py-4 border-b border-white/[0.03]">
        <div className="relative flex items-center justify-center w-9 h-9 rounded-xl bg-success/10 border border-success/20 shrink-0">
          <ShieldAlert className="text-success" size={18} strokeWidth={1.5} />
          <div className="absolute inset-0 rounded-xl bg-success/10 animate-pulse-glow" />
        </div>
        {open && (
          <motion.div
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.2 }}
            className="flex flex-col"
          >
            <span className="font-bold text-base tracking-tight gradient-text-green leading-tight">Lucy</span>
            <span className="text-[9px] font-mono text-base-content/30 uppercase tracking-wider">Defense Platform</span>
          </motion.div>
        )}
      </div>

      {/* Nav sections */}
      <nav className="flex flex-col gap-0.5 p-2 flex-1 overflow-y-auto scrollbar-thin">
        {sections.map((section) => (
          <div key={section.title}>
            <SectionHeader title={section.title} isOpen={open} />
            {section.items.map((item) => (
              <NavItem
                key={item.to}
                item={item}
                isOpen={open}
                isActive={location.pathname === item.to || (item.to !== '/' && location.pathname.startsWith(item.to))}
              />
            ))}
          </div>
        ))}
      </nav>

      {/* Copilot button */}
      <div className="p-2 border-t border-white/[0.03]">
        <button
          onClick={toggleCopilot}
          className={`group relative flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-200 w-full ${
            copilotOpen
              ? 'bg-success/15 text-success shadow-[0_0_12px_rgba(0,255,157,0.12)]'
              : 'text-base-content/60 hover:text-success hover:bg-success/5'
          }`}
        >
          <div className={`relative flex items-center justify-center w-8 h-8 rounded-lg transition-all duration-200 shrink-0 ${
            copilotOpen ? 'bg-success/20 text-success' : 'bg-base-300/30 text-base-content/40 group-hover:text-success'
          }`}>
            <Sparkles size={16} strokeWidth={1.5} />
            {copilotOpen && <div className="absolute inset-0 rounded-lg bg-success/10 animate-pulse-glow" />}
          </div>
          {open && (
            <motion.span
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.2 }}
              className="truncate"
            >
              AI Copilot
            </motion.span>
          )}
          {open && copilotOpen && (
            <kbd className="kbd kbd-xs ml-auto text-[8px] opacity-50">Ctrl+J</kbd>
          )}
        </button>
      </div>

      {/* Footer */}
      <div className="px-3 py-3 border-t border-white/[0.03]">
        {open ? (
          <div className="flex items-center justify-between text-[9px] text-base-content/20 font-mono">
            <span>v2.0.0</span>
            <div className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-success animate-pulse-glow" />
              <span>SYSTEM READY</span>
            </div>
          </div>
        ) : (
          <div className="flex justify-center">
            <div className="w-1.5 h-1.5 rounded-full bg-success animate-pulse-glow" />
          </div>
        )}
      </div>
    </aside>
  )
}
