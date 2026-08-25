import { lazy, Suspense } from 'react'
import { createBrowserRouter, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import { useAuthStore } from './stores/authStore'

const RouterErrorElement = lazy(() => import('./components/RouterErrorElement'))
const Login          = lazy(() => import('./pages/Login'))
const Agents         = lazy(() => import('./pages/Agents'))
const AgentDetail    = lazy(() => import('./pages/AgentDetail'))
const Chat           = lazy(() => import('./pages/Chat'))
const AgentBuilder   = lazy(() => import('./pages/AgentBuilder'))
const Packs          = lazy(() => import('./pages/Packs'))
const Settings       = lazy(() => import('./pages/Settings'))

// Secondary routes — accessible via URL but not in the simplified sidebar
const Dashboard      = lazy(() => import('./pages/Dashboard'))
const Mission        = lazy(() => import('./pages/Mission'))
const Strategy       = lazy(() => import('./pages/Strategy'))
const ModuleStore    = lazy(() => import('./pages/ModuleStore'))
const Library        = lazy(() => import('./pages/Library'))
const TimelineBuilder = lazy(() => import('./pages/TimelineBuilder'))
const ScriptBuilder = lazy(() => import('./pages/ScriptBuilder'))
const Terminal       = lazy(() => import('./pages/Terminal'))
const MapPage        = lazy(() => import('./pages/MapPage'))
const Tasks          = lazy(() => import('./pages/Tasks'))
const TaskDetail     = lazy(() => import('./pages/TaskDetail'))
const GanttView      = lazy(() => import('./pages/GanttView'))
const Setup          = lazy(() => import('./pages/Setup'))
const RemoteDesktop  = lazy(() => import('./pages/RemoteDesktop'))
const Reports        = lazy(() => import('./pages/Reports'))
const Defense        = lazy(() => import('./pages/Defense'))
const Alerts         = lazy(() => import('./pages/Alerts'))
const Findings       = lazy(() => import('./pages/Findings'))
const Groups         = lazy(() => import('./pages/Groups'))
const Credentials    = lazy(() => import('./pages/Credentials'))
const Logs           = lazy(() => import('./pages/Logs'))
const RBAC           = lazy(() => import('./pages/RBAC'))
const C2Profiles     = lazy(() => import('./pages/C2Profiles'))
const AIAgent        = lazy(() => import('./pages/AIAgent'))
const AIChat         = lazy(() => import('./pages/AIChat'))

function Guard({ children }: { children: React.ReactNode }) {
  const auth = useAuthStore((s) => s.isAuthenticated)
  if (!auth) return <Navigate to="/login" replace />
  return <>{children}</>
}

const Spin = () => (
  <div className="flex items-center justify-center h-full">
    <span className="loading loading-spinner loading-lg text-success" />
  </div>
)

export const router = createBrowserRouter([
  { path: '/login', element: <Suspense fallback={<Spin />}><Login /></Suspense> },
  {
    path: '/',
    element: <Guard><Layout /></Guard>,
    errorElement: <Suspense fallback={<Spin />}><RouterErrorElement /></Suspense>,
    children: [
      // === Primary routes (in sidebar) ===
      { index: true,              element: <Navigate to="/agents" replace /> },
      { path: 'agents',           element: <Suspense fallback={<Spin />}><Agents /></Suspense> },
      { path: 'agents/:id',       element: <Suspense fallback={<Spin />}><AgentDetail /></Suspense> },
      { path: 'chat',             element: <Suspense fallback={<Spin />}><Chat /></Suspense> },
      { path: 'builder',          element: <Suspense fallback={<Spin />}><AgentBuilder /></Suspense> },
      { path: 'packs',            element: <Suspense fallback={<Spin />}><Packs /></Suspense> },
      { path: 'settings',         element: <Suspense fallback={<Spin />}><Settings /></Suspense> },

      // === Secondary routes (accessible via URL, not in sidebar) ===
      { path: 'dashboard',        element: <Suspense fallback={<Spin />}><Dashboard /></Suspense> },
      { path: 'mission',          element: <Suspense fallback={<Spin />}><Mission /></Suspense> },
      { path: 'strategy',         element: <Suspense fallback={<Spin />}><Strategy /></Suspense> },
      { path: 'tasks',            element: <Suspense fallback={<Spin />}><Tasks /></Suspense> },
      { path: 'tasks/:id',        element: <Suspense fallback={<Spin />}><TaskDetail /></Suspense> },
      { path: 'modules',          element: <Navigate to="/library" replace /> },
      { path: 'library',          element: <Suspense fallback={<Spin />}><Library /></Suspense> },
      { path: 'library/:id',      element: <Suspense fallback={<Spin />}><Library /></Suspense> },
      { path: 'timelines',        element: <Suspense fallback={<Spin />}><TimelineBuilder /></Suspense> },
      { path: 'script-builder',    element: <Suspense fallback={<Spin />}><ScriptBuilder /></Suspense> },
      { path: 'terminal',         element: <Suspense fallback={<Spin />}><Terminal /></Suspense> },
      { path: 'map',              element: <Suspense fallback={<Spin />}><MapPage /></Suspense> },
      { path: 'gantt',            element: <Suspense fallback={<Spin />}><GanttView /></Suspense> },
      { path: 'setup',            element: <Suspense fallback={<Spin />}><Setup /></Suspense> },
      { path: 'remote/:id',       element: <Suspense fallback={<Spin />}><RemoteDesktop /></Suspense> },
      { path: 'reports',          element: <Suspense fallback={<Spin />}><Reports /></Suspense> },
      { path: 'defense',          element: <Suspense fallback={<Spin />}><Defense /></Suspense> },
      { path: 'alerts',           element: <Suspense fallback={<Spin />}><Alerts /></Suspense> },
      { path: 'findings',         element: <Suspense fallback={<Spin />}><Findings /></Suspense> },
      { path: 'groups',           element: <Suspense fallback={<Spin />}><Groups /></Suspense> },
      { path: 'credentials',      element: <Suspense fallback={<Spin />}><Credentials /></Suspense> },
      { path: 'logs',             element: <Suspense fallback={<Spin />}><Logs /></Suspense> },
      { path: 'rbac',             element: <Suspense fallback={<Spin />}><RBAC /></Suspense> },
      { path: 'c2-profiles',      element: <Suspense fallback={<Spin />}><C2Profiles /></Suspense> },
      { path: 'ai-agent',         element: <Suspense fallback={<Spin />}><AIAgent /></Suspense> },
      { path: 'ai-chat',          element: <Suspense fallback={<Spin />}><AIChat /></Suspense> },
    ],
  },
])
