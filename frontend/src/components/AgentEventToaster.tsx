import { useEffect, useRef } from 'react'
import { useWebSocket } from '../hooks/useWebSocket'
import { useToast } from '../contexts/ToastContext'
import { useAgentStore } from '../stores/agentStore'
import { useUIStore } from '../stores/uiStore'

/**
 * Listens to agent WebSocket events and fires human-readable toasts.
 * This closes the loop: agent connects → operator gets a toast → can act immediately.
 */
export function AgentEventToaster() {
  const { on } = useWebSocket()
  const { addToast } = useToast()
  const agents = useAgentStore((s) => s.agentsArray)
  const openAgent = useUIStore((s) => s.openAgent)
  const agentsRef = useRef(agents)
  agentsRef.current = agents

  // Keep a set of recently toasted agent IDs to avoid duplicate connect toasts
  const toasted = useRef<Set<string>>(new Set())

  useEffect(() => {
    const unsubConnect = on('agent_connected', (msg: any) => {
      const p = msg.payload || {}
      const aid = p.agent_id || msg.agent_id
      if (!aid) return
      const hostname = p.hostname || agentsRef.current.find((a: any) => a.id === aid)?.hostname || aid.slice(0, 8)
      addToast({
        type: 'success',
        title: `Agent connected: ${hostname}`,
        message: `${p.os || 'unknown OS'} · ${p.username || 'unknown user'}`,
        duration: 5000,
        onClick: () => openAgent(aid),
      })
      toasted.current.add(aid)
    })

    const unsubDisconnect = on('agent_disconnected', (msg: any) => {
      const p = msg.payload || {}
      const aid = p.agent_id || msg.agent_id
      if (!aid) return
      const hostname = agentsRef.current.find((a: any) => a.id === aid)?.hostname || aid.slice(0, 8)
      addToast({
        type: 'warning',
        title: `Agent disconnected: ${hostname}`,
        message: 'Connection lost — tasks will be queued offline.',
        duration: 5000,
        onClick: () => openAgent(aid),
      })
    })

    const unsubResult = on('result', (msg: any) => {
      const p = msg.payload || {}
      const status = p.status || 'completed'
      const module = p.module || p.task_module || 'task'
      const aid = p.agent_id || msg.agent_id
      const hostname = agentsRef.current.find((a: any) => a.id === aid)?.hostname || (aid ? aid.slice(0, 8) : 'agent')

      if (status === 'failed') {
        addToast({
          type: 'error',
          title: `Task failed on ${hostname}`,
          message: `${module}: ${p.error || 'unknown error'}`,
          duration: 6000,
          onClick: () => aid && openAgent(aid),
        })
      }
      // Don't toast every successful task — too noisy. Only toast notable modules.
      if (status === 'completed' && ['screenshot', 'keylog', 'credential_dump', 'kerberoast', 'clipboard'].includes(module)) {
        addToast({
          type: 'info',
          title: `${module} result received from ${hostname}`,
          message: 'Click to view in agent panel',
          duration: 4000,
          onClick: () => aid && openAgent(aid),
        })
      }
    })

    const unsubAlert = on('alert', (msg: any) => {
      const p = msg.payload || {}
      const severity = p.severity || 'info'
      const type = severity === 'critical' ? 'error' : severity === 'warning' ? 'warning' : 'info'
      addToast({
        type: type as any,
        title: p.title || 'Alert',
        message: p.message || '',
        duration: 6000,
      })
    })

    const unsubPrediction = on('predictive_alert', (msg: any) => {
      const p = msg.payload || {}
      addToast({
        type: 'warning',
        title: `Predictive: ${p.title || 'anomaly detected'}`,
        message: p.message || '',
        duration: 7000,
      })
    })

    const unsubOpConnect = on('operator_connected', (msg: any) => {
      const p = msg.payload || {}
      addToast({
        type: 'info',
        title: `${p.username || 'Operator'} joined`,
        message: `${p.role || 'operator'} · now collaborating`,
        duration: 4000,
      })
    })

    const unsubOpDisconnect = on('operator_disconnected', (msg: any) => {
      const p = msg.payload || {}
      addToast({
        type: 'info',
        title: `${p.username || 'Operator'} left`,
        message: 'Session ended',
        duration: 3000,
      })
    })

    const unsubOpBroadcast = on('operator_broadcast', (msg: any) => {
      const p = msg.payload || {}
      addToast({
        type: 'info',
        title: `Message from ${p.from || 'operator'}`,
        message: p.message || '',
        duration: 6000,
      })
    })

    return () => {
      unsubConnect()
      unsubDisconnect()
      unsubResult()
      unsubAlert()
      unsubPrediction()
      unsubOpConnect()
      unsubOpDisconnect()
      unsubOpBroadcast()
    }
  }, [on, addToast])

  return null
}
