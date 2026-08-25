import { create } from 'zustand'

type CopilotTab = 'chat' | 'web' | 'explorer' | 'poc'

interface CopilotState {
  open: boolean
  activeTab: CopilotTab
  sessionId: string
  /** Current page context (e.g. "agents", "tasks/123") for richer AI responses */
  contextPage: string | null
  /** Pre-filled input from another component (e.g. "Analyse cet agent: FBOX") */
  prefillMessage: string | null
  toggleOpen: () => void
  setOpen: (v: boolean) => void
  setTab: (t: CopilotTab) => void
  setContextPage: (p: string | null) => void
  setPrefill: (msg: string | null) => void
  openWithMessage: (msg: string) => void
}

export const useCopilotStore = create<CopilotState>((set) => ({
  open: false,
  activeTab: 'chat',
  sessionId: 'copilot',
  contextPage: null,
  prefillMessage: null,

  toggleOpen: () => set((s) => ({ open: !s.open })),
  setOpen: (v) => set({ open: v }),
  setTab: (t) => set({ activeTab: t }),
  setContextPage: (p) => set({ contextPage: p }),
  setPrefill: (msg) => set({ prefillMessage: msg }),
  openWithMessage: (msg) => set({ open: true, activeTab: 'chat', prefillMessage: msg }),
}))
