import { Menu, Moon, Sun, LogOut, User, Building2, ChevronDown } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { useUIStore } from '../stores/uiStore'
import { useAuthStore } from '../stores/authStore'
import { useTenantStore } from '../stores/tenantStore'
import { listTenants } from '../api/tenants'
import { useNavigate } from 'react-router-dom'
import { OperatorPresence } from './OperatorPresence'

export default function Navbar() {
  const { toggleSidebar, theme, setTheme } = useUIStore()
  const { user, logout } = useAuthStore()
  const { activeTenant, setActiveTenant, clearTenant } = useTenantStore()
  const navigate = useNavigate()

  const isSuperAdmin = user?.role === 'superadmin'

  const { data: tenants = [] } = useQuery({
    queryKey: ['tenants'],
    queryFn: listTenants,
    enabled: isSuperAdmin,
  })

  const handleLogout = () => {
    logout()
    clearTenant()
    navigate('/login')
  }

  return (
    <header className="navbar bg-base-200 border-b border-base-300 px-4 h-14 min-h-0 sticky top-0 z-10">
      <div className="flex-1 gap-2">
        <button className="btn btn-ghost btn-sm btn-square" onClick={toggleSidebar}>
          <Menu size={18} />
        </button>
      </div>
      <div className="flex-none gap-2 items-center">

        {/* Tenant selector — superadmin can switch tenants */}
        {isSuperAdmin && (
          <div className="dropdown dropdown-end">
            <label tabIndex={0} className="btn btn-ghost btn-sm gap-1 border border-base-300">
              <Building2 size={14} />
              <span className="text-xs hidden sm:inline max-w-[120px] truncate">
                {activeTenant ? activeTenant.name : 'All Tenants'}
              </span>
              <ChevronDown size={12} />
            </label>
            <ul tabIndex={0} className="dropdown-content menu p-2 shadow bg-base-200 rounded-box w-52 border border-base-300 z-50">
              <li>
                <a onClick={() => clearTenant()} className={!activeTenant ? 'active' : ''}>
                  <Building2 size={13} /> All Tenants
                </a>
              </li>
              {tenants.map(t => (
                <li key={t.id}>
                  <a
                    onClick={() => setActiveTenant(t)}
                    className={activeTenant?.id === t.id ? 'active' : ''}
                  >
                    <span className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: t.color }} />
                    <span className="truncate">{t.name}</span>
                  </a>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Regular user — show their tenant badge */}
        {!isSuperAdmin && user?.tenant_id && (
          <span className="badge badge-outline badge-sm gap-1 hidden sm:flex">
            <Building2 size={10} />
            {activeTenant?.name ?? 'Tenant'}
          </span>
        )}

        {/* Multi-player operator presence */}
        <OperatorPresence />

        <button
          className="btn btn-ghost btn-sm btn-square"
          onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
          title="Toggle theme"
        >
          {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
        </button>

        <div className="dropdown dropdown-end">
          <label tabIndex={0} className="btn btn-ghost btn-sm gap-1">
            <User size={16} />
            <span className="text-sm hidden sm:inline">{user?.username ?? 'User'}</span>
          </label>
          <ul tabIndex={0} className="dropdown-content menu p-2 shadow bg-base-200 rounded-box w-40 border border-base-300">
            <li><a onClick={handleLogout}><LogOut size={14} />Logout</a></li>
          </ul>
        </div>
      </div>
    </header>
  )
}
