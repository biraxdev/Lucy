import { create } from 'zustand'

type Theme = 'dark' | 'light'

/**
 * Global UI store.
 * Manages sidebar, theme, and the slide-in agent drawer so any page
 * can open an agent detail panel without a route change — enabling
 * circular workflow.
 */

interface UIState {
  // --- Sidebar ---
  sidebarOpen: boolean
  toggleSidebar: () => void

  // --- Theme ---
  theme: Theme
  setTheme: (t: Theme) => void

  // --- Agent drawer (slide-in panel) ---
  /** Agent ID currently shown in the drawer (null = closed) */
  drawerAgentId: string | null
  /** Stack of previously opened agents for "back" navigation within the drawer */
  drawerHistory: string[]
  /** Whether the drawer is visually open */
  drawerOpen: boolean

  openAgent: (agentId: string) => void
  closeDrawer: () => void
  goBack: () => void
  /** True if there's a previous agent to go back to */
  canGoBack: () => boolean
}

export const useUIStore = create<UIState>((set, get) => ({
  // --- Sidebar ---
  sidebarOpen: true,
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),

  // --- Theme ---
  theme: 'dark',
  setTheme: (t) => set({ theme: t }),

  // --- Agent drawer ---
  drawerAgentId: null,
  drawerHistory: [],
  drawerOpen: false,

  openAgent: (agentId: string) => {
    const state = get()
    const history = state.drawerAgentId && state.drawerAgentId !== agentId
      ? [...state.drawerHistory, state.drawerAgentId]
      : state.drawerHistory
    set({
      drawerAgentId: agentId,
      drawerHistory: history,
      drawerOpen: true,
    })
  },

  closeDrawer: () => {
    set({ drawerOpen: false })
    // Clear after animation
    setTimeout(() => {
      const s = get()
      if (!s.drawerOpen) {
        set({ drawerAgentId: null, drawerHistory: [] })
      }
    }, 300)
  },

  goBack: () => {
    const state = get()
    if (state.drawerHistory.length === 0) {
      set({ drawerOpen: false })
      setTimeout(() => set({ drawerAgentId: null, drawerHistory: [] }), 300)
      return
    }
    const history = [...state.drawerHistory]
    const prevId = history.pop()!
    set({
      drawerAgentId: prevId,
      drawerHistory: history,
      drawerOpen: true,
    })
  },

  canGoBack: () => get().drawerHistory.length > 0,
}))
