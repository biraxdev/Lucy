import { create } from 'zustand'
import type { Agent, AgentStatus } from '../types/agent'

interface AgentEntities {
  byId: Record<string, Agent>
  ids: string[]
  agentsArray: Agent[]
}

interface AgentState extends AgentEntities {
  selectedId: string | null
  setAgents: (agents: Agent[]) => void
  upsertAgent: (agent: Partial<Agent> & { id: string }) => void
  removeAgent: (id: string) => void
  setSelected: (agent: Agent | null) => void
  updateStatus: (id: string, status: AgentStatus) => void
  getAgentById: (id: string) => Agent | undefined
}

function normalizeAgents(agents: Agent[]): AgentEntities {
  const byId: Record<string, Agent> = {}
  const ids: string[] = []
  for (const a of agents) {
    byId[a.id] = a
    ids.push(a.id)
  }
  return { byId, ids, agentsArray: agents }
}

export const useAgentStore = create<AgentState>((set, get) => ({
  byId: {},
  ids: [],
  agentsArray: [],
  selectedId: null,

  setAgents: (agents) => set(normalizeAgents(agents)),

  upsertAgent: (agent) =>
    set((s) => {
      const existing = s.byId[agent.id]
      const merged: Agent = existing ? { ...existing, ...agent } : (agent as Agent)
      const isNew = !s.byId[agent.id]
      const ids = isNew ? [agent.id, ...s.ids] : s.ids
      const byId = { ...s.byId, [agent.id]: merged }
      return { byId, ids, agentsArray: ids.map((id) => byId[id]) }
    }),

  removeAgent: (id) =>
    set((s) => {
      if (!s.byId[id]) return s
      const { [id]: _, ...rest } = s.byId
      const ids = s.ids.filter((x) => x !== id)
      return {
        byId: rest,
        ids,
        agentsArray: ids.map((i) => rest[i]),
        selectedId: s.selectedId === id ? null : s.selectedId,
      }
    }),

  setSelected: (agent) => set({ selectedId: agent?.id ?? null }),

  updateStatus: (id, status) =>
    set((s) => {
      const agent = s.byId[id]
      if (!agent) return s
      const byId = { ...s.byId, [id]: { ...agent, status, last_seen: new Date().toISOString() } }
      return { byId, agentsArray: s.ids.map((i) => byId[i]) }
    }),

  getAgentById: (id) => get().byId[id],
}))
