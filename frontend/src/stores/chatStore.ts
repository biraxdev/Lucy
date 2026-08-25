import { create } from 'zustand'
import type { ChatMessage } from '../types/chat'

interface ChatState {
  messages: ChatMessage[]
  pending: boolean
  unread: number
  draft: string
  setMessages: (messages: ChatMessage[]) => void
  appendMessage: (message: ChatMessage) => void
  updateMessage: (id: string, updater: (msg: ChatMessage) => ChatMessage) => void
  setPending: (pending: boolean) => void
  setDraft: (draft: string) => void
  clearUnread: () => void
  incrementUnread: () => void
  markAllRead: () => void
}

export const useChatStore = create<ChatState>((set) => ({
  messages: [],
  pending: false,
  unread: 0,
  draft: '',
  setMessages: (messages) => set({ messages }),
  appendMessage: (message) =>
    set((s) => ({
      messages: [...s.messages, message],
      unread: s.unread + 1,
    })),
  updateMessage: (id, updater) =>
    set((s) => ({
      messages: s.messages.map((m) => (m.id === id ? updater(m) : m)),
    })),
  setPending: (pending) => set({ pending }),
  setDraft: (draft) => set({ draft }),
  clearUnread: () => set({ unread: 0 }),
  incrementUnread: () => set((s) => ({ unread: s.unread + 1 })),
  markAllRead: () => set({ unread: 0 }),
}))
