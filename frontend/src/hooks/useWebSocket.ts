import { useEffect, useCallback } from 'react'
import { useAuthStore } from '../stores/authStore'
import { useAgentStore } from '../stores/agentStore'
import { useTaskStore } from '../stores/taskStore'

export type WSMessage = { type: string; payload: unknown; agent_id?: string; task_id?: string }
export type Handler = (msg: WSMessage) => void

const MIN_RECONNECT_DELAY = 1000
const MAX_RECONNECT_DELAY = 30000
const HEARTBEAT_INTERVAL = 25000
const HEARTBEAT_TIMEOUT = 10000

interface SocketManager {
  socket: WebSocket | null
  reconnectTimer: ReturnType<typeof setTimeout> | null
  heartbeatTimer: ReturnType<typeof setInterval> | null
  pongTimer: ReturnType<typeof setTimeout> | null
  reconnectDelay: number
  messageQueue: object[]
  handlers: Map<string, Set<Handler>>
  connecting: boolean
}

const manager: SocketManager = {
  socket: null,
  reconnectTimer: null,
  heartbeatTimer: null,
  pongTimer: null,
  reconnectDelay: MIN_RECONNECT_DELAY,
  messageQueue: [],
  handlers: new Map(),
  connecting: false,
}

function getWsUrl(token: string) {
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
  return `${proto}://${window.location.host}/ws/frontend?token=${token}`
}

function emit(type: string, msg: WSMessage) {
  const sets = [manager.handlers.get(type), manager.handlers.get('*')]
  sets.forEach((set) => set?.forEach((h) => h(msg)))
}

function flushQueue() {
  while (manager.messageQueue.length && manager.socket?.readyState === WebSocket.OPEN) {
    const msg = manager.messageQueue.shift()
    if (msg) manager.socket.send(JSON.stringify(msg))
  }
}

function sendWS(msg: object) {
  if (manager.socket?.readyState === WebSocket.OPEN) {
    manager.socket.send(JSON.stringify(msg))
  } else {
    if (manager.messageQueue.length < 256) manager.messageQueue.push(msg)
  }
}

function clearHeartbeat() {
  if (manager.heartbeatTimer) {
    clearInterval(manager.heartbeatTimer)
    manager.heartbeatTimer = null
  }
  if (manager.pongTimer) {
    clearTimeout(manager.pongTimer)
    manager.pongTimer = null
  }
}

function scheduleReconnect() {
  if (manager.reconnectTimer) return
  manager.reconnectDelay = Math.min(manager.reconnectDelay * 2, MAX_RECONNECT_DELAY)
  manager.reconnectTimer = setTimeout(() => {
    manager.reconnectTimer = null
    const currentToken = useAuthStore.getState().accessToken
    if (currentToken) connect(currentToken)
  }, manager.reconnectDelay)
}

function connect(token: string) {
  if (manager.socket?.readyState === WebSocket.OPEN || manager.connecting) return
  manager.connecting = true

  const ws = new WebSocket(getWsUrl(token))
  manager.socket = ws

  ws.onopen = () => {
    manager.connecting = false
    manager.reconnectDelay = MIN_RECONNECT_DELAY
    clearHeartbeat()
    manager.heartbeatTimer = setInterval(() => {
      sendWS({ type: 'ping', timestamp: Date.now() })
      manager.pongTimer = setTimeout(() => {
        manager.socket?.close()
      }, HEARTBEAT_TIMEOUT)
    }, HEARTBEAT_INTERVAL)
    flushQueue()
  }

  ws.onmessage = (ev) => {
    try {
      const msg: WSMessage = JSON.parse(ev.data)
      if (msg.type === 'pong' && manager.pongTimer) {
        clearTimeout(manager.pongTimer)
        manager.pongTimer = null
        return
      }
      emit(msg.type, msg)
    } catch {}
  }

  ws.onclose = () => {
    // Ignore close events from stale sockets that have been replaced
    if (manager.socket !== ws) return
    manager.connecting = false
    clearHeartbeat()
    if (useAuthStore.getState().isAuthenticated) {
      scheduleReconnect()
    }
  }

  ws.onerror = () => {
    if (manager.socket !== ws) return
    manager.connecting = false
    ws.close()
  }
}

function disconnect() {
  if (manager.reconnectTimer) {
    clearTimeout(manager.reconnectTimer)
    manager.reconnectTimer = null
  }
  clearHeartbeat()
  manager.socket?.close()
  manager.socket = null
}

export function onWS(type: string, handler: Handler) {
  if (!manager.handlers.has(type)) manager.handlers.set(type, new Set())
  manager.handlers.get(type)!.add(handler)
  return () => {
    manager.handlers.get(type)?.delete(handler)
  }
}

export function sendWsMessage(msg: object) {
  sendWS(msg)
}

export function useWebSocket() {
  const token = useAuthStore((s) => s.accessToken)
  const upsertAgent = useAgentStore((s) => s.upsertAgent)
  const upsertTask = useTaskStore((s) => s.upsertTask)

  useEffect(() => {
    if (!token) {
      disconnect()
      return
    }
    // Always start fresh: tear down any stale socket from a previous token
    disconnect()
    connect(token)

    const unsubHeartbeat = onWS('heartbeat', (msg) => {
      if (msg.agent_id) {
        upsertAgent({ id: msg.agent_id, status: 'online', ...(msg.payload as object) } as any)
      }
    })

    const unsubResult = onWS('result', (msg) => {
      const payload = msg.payload as any
      if (payload?.id || payload?.task_id) {
        upsertTask({ id: payload.id ?? payload.task_id, ...payload })
      }
    })

    const unsubAgentConnected = onWS('agent_connected', (msg) => {
      const payload = msg.payload as any
      if (payload?.agent_id) upsertAgent({ id: payload.agent_id, status: 'online' })
    })

    const unsubAgentDisconnected = onWS('agent_disconnected', (msg) => {
      const payload = msg.payload as any
      if (payload?.agent_id) upsertAgent({ id: payload.agent_id, status: 'offline' })
    })

    return () => {
      unsubHeartbeat()
      unsubResult()
      unsubAgentConnected()
      unsubAgentDisconnected()
    }
  }, [token, upsertAgent, upsertTask])

  const subscribe = useCallback((channel: string) => {
    sendWS({ type: 'subscribe', payload: { channel } })
  }, [])

  const unsubscribe = useCallback((channel: string) => {
    sendWS({ type: 'unsubscribe', payload: { channel } })
  }, [])

  const on = useCallback((type: string, handler: Handler) => onWS(type, handler), [])

  return { subscribe, unsubscribe, on, send: sendWsMessage }
}
