import { create } from 'zustand'
import type { Task } from '../types/task'

interface TaskEntities {
  byId: Record<string, Task>
  ids: string[]
  tasksArray: Task[]
}

interface TaskState extends TaskEntities {
  selectedId: string | null
  setTasks: (tasks: Task[]) => void
  upsertTask: (task: Partial<Task> & { id: string }) => void
  removeTask: (id: string) => void
  setSelected: (id: string | null) => void
  getTaskById: (id: string) => Task | undefined
  tasksForAgent: (agentId: string) => Task[]
}

function normalizeTasks(tasks: Task[]): TaskEntities {
  const byId: Record<string, Task> = {}
  const ids: string[] = []
  for (const t of tasks) {
    byId[t.id] = t
    ids.push(t.id)
  }
  return { byId, ids, tasksArray: tasks }
}

export const useTaskStore = create<TaskState>((set, get) => ({
  byId: {},
  ids: [],
  tasksArray: [],
  selectedId: null,

  setTasks: (tasks) => set(normalizeTasks(tasks)),

  upsertTask: (task) =>
    set((s) => {
      const existing = s.byId[task.id]
      const merged: Task = existing ? { ...existing, ...task } : (task as Task)
      const isNew = !s.byId[task.id]
      const ids = isNew ? [task.id, ...s.ids] : s.ids
      const byId = { ...s.byId, [task.id]: merged }
      return { byId, ids, tasksArray: ids.map((id) => byId[id]) }
    }),

  removeTask: (id) =>
    set((s) => {
      if (!s.byId[id]) return s
      const { [id]: _, ...rest } = s.byId
      const ids = s.ids.filter((x) => x !== id)
      return {
        byId: rest,
        ids,
        tasksArray: ids.map((i) => rest[i]),
        selectedId: s.selectedId === id ? null : s.selectedId,
      }
    }),

  setSelected: (id) => set({ selectedId: id }),

  getTaskById: (id) => get().byId[id],

  tasksForAgent: (agentId) =>
    get().tasksArray.filter((t) => t.agent_id === agentId),
}))
