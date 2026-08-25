import { NavLink } from 'react-router-dom'
import {
  Server, MessageCircle, Hammer, Settings,
  ShieldAlert,
} from 'lucide-react'
import { useUIStore } from '../stores/uiStore'

const links = [
  { to: '/agents',   icon: Server,         label: 'Agents' },
  { to: '/chat',     icon: MessageCircle,  label: 'Chat Lucy' },
  { to: '/builder',  icon: Hammer,         label: 'Builder' },
  { to: '/settings', icon: Settings,       label: 'Settings' },
]

export default function Sidebar() {
  const open = useUIStore((s) => s.sidebarOpen)

  return (
    <aside
      className={`flex flex-col bg-base-200 border-r border-base-300 transition-all duration-200 ${open ? 'w-56' : 'w-16'} shrink-0 h-screen sticky top-0`}
    >
      {/* Logo */}
      <div className="flex items-center gap-2 px-4 py-4 border-b border-base-300">
        <ShieldAlert className="text-success shrink-0" size={22} />
        {open && <span className="font-bold text-lg tracking-wide text-success">Lucy C2</span>}
      </div>

      {/* Nav — flat, no sections */}
      <nav className="flex flex-col gap-1 p-2 flex-1 overflow-y-auto scrollbar-thin">
        {links.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors
               ${isActive ? 'bg-success/20 text-success' : 'text-base-content/70 hover:bg-base-300 hover:text-base-content'}`
            }
          >
            <Icon size={18} className="shrink-0" />
            {open && <span>{label}</span>}
          </NavLink>
        ))}
      </nav>

      {/* Footer — version */}
      {open && (
        <div className="px-4 py-2 border-t border-base-300 text-[10px] text-base-content/30">
          v1.0.0 · Lucy C2
        </div>
      )}
    </aside>
  )
}
