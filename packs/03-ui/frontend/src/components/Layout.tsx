import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'
import Navbar from './Navbar'
import { CommandPalette } from './CommandPalette'
import { AgentDrawer } from './AgentDrawer'
import { ToastProvider } from '../contexts/ToastContext'
import { AgentEventToaster } from './AgentEventToaster'

export default function Layout() {
  return (
    <ToastProvider>
      <AgentEventToaster />
      <CommandPalette />
      <AgentDrawer />
      <div className="flex h-screen overflow-hidden">
        <Sidebar />
        <div className="flex flex-col flex-1 overflow-hidden">
          <Navbar />
          <main className="flex-1 overflow-y-auto scrollbar-thin">
            <Outlet />
          </main>
        </div>
      </div>
    </ToastProvider>
  )
}
