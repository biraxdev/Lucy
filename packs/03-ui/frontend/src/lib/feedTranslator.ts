/**
 * Translates raw WebSocket events into human-readable feed items.
 * This replaces the old JSON.stringify(msg.payload).slice(0,80) approach.
 */

import {
  Heart, Wifi, WifiOff, CheckCircle, XCircle, Terminal,
  Monitor, KeyRound, Bug, Activity, AlertTriangle, Bell, FileText, Zap, Users,
} from 'lucide-react'

export interface FeedItem {
  id: string
  type: string
  message: string
  ts: string
  icon: React.ElementType
  color: string
  agentName?: string
}

const AGENT_NAME_CACHE: Record<string, string> = {}

function agentName(id: string | undefined, agents?: any[]): string {
  if (!id) return 'Unknown'
  if (AGENT_NAME_CACHE[id]) return AGENT_NAME_CACHE[id]
  const a = agents?.find((x: any) => x.id === id)
  const name = a?.hostname || id.slice(0, 8)
  AGENT_NAME_CACHE[id] = name
  return name
}

export function translateEvent(
  msg: { type: string; payload: any; agent_id?: string },
  agents?: any[]
): FeedItem | null {
  const { type, payload } = msg
  const ts = new Date().toLocaleTimeString()
  const id = Math.random().toString(36).slice(2)
  const aid = msg.agent_id || payload?.agent_id

  switch (type) {
    case 'heartbeat':
      return {
        id, type, ts,
        icon: Heart,
        color: 'text-emerald-400',
        agentName: agentName(aid, agents),
        message: `Heartbeat from ${agentName(aid, agents)} — CPU ${payload?.cpu ?? '?'}%, RAM ${(payload?.ram_available ? (payload.ram_available / 1024 / 1024 / 1024).toFixed(1) : '?')} GB free`,
      }

    case 'agent_connected':
      return {
        id, type, ts,
        icon: Wifi,
        color: 'text-success',
        agentName: agentName(aid, agents),
        message: `${payload?.hostname || agentName(aid, agents)} connected — ${payload?.os || 'unknown'} · ${payload?.username || 'unknown user'}`,
      }

    case 'agent_disconnected':
      return {
        id, type, ts,
        icon: WifiOff,
        color: 'text-rose-400',
        agentName: agentName(aid, agents),
        message: `${agentName(aid, agents)} went offline — tasks will be queued`,
      }

    case 'result': {
      const status = payload?.status || 'completed'
      const module = payload?.module || 'task'
      const succeeded = status !== 'failed'
      return {
        id, type, ts,
        icon: succeeded ? CheckCircle : XCircle,
        color: succeeded ? 'text-emerald-400' : 'text-rose-400',
        agentName: agentName(aid, agents),
        message: succeeded
          ? `${module} completed on ${agentName(aid, agents)}`
          : `${module} failed on ${agentName(aid, agents)}: ${payload?.error || 'unknown error'}`,
      }
    }

    case 'log':
      return {
        id, type, ts,
        icon: Terminal,
        color: payload?.level === 'ERROR' ? 'text-rose-400' : payload?.level === 'WARNING' ? 'text-amber-400' : 'text-base-content/50',
        agentName: agentName(aid, agents),
        message: `[${payload?.level || 'INFO'}] ${agentName(aid, agents)}: ${payload?.message || ''}`.slice(0, 120),
      }

    case 'alert':
      return {
        id, type, ts,
        icon: AlertTriangle,
        color: payload?.severity === 'critical' ? 'text-rose-400' : 'text-amber-400',
        message: `Alert: ${payload?.title || 'unknown'} — ${payload?.message || ''}`.slice(0, 120),
      }

    case 'predictive_alert':
      return {
        id, type, ts,
        icon: Zap,
        color: 'text-amber-400',
        message: `Predictive: ${payload?.title || 'anomaly'} — ${payload?.message || ''}`.slice(0, 120),
      }

    case 'operator_connected':
      return {
        id, type, ts,
        icon: Users,
        color: 'text-sky-400',
        message: `${payload?.username || 'Operator'} joined (${payload?.role || 'operator'})`,
      }

    case 'operator_disconnected':
      return {
        id, type, ts,
        icon: Users,
        color: 'text-base-content/40',
        message: `${payload?.username || 'Operator'} left the session`,
      }

    case 'operator_broadcast':
      return {
        id, type, ts,
        icon: Users,
        color: 'text-sky-400',
        message: `${payload?.from || 'Operator'}: ${payload?.message || ''}`.slice(0, 120),
      }

    case 'chat':
      return null // Chat messages are handled by the Chat page, not the feed

    case 'credential':
      return {
        id, type, ts,
        icon: KeyRound,
        color: 'text-rose-400',
        agentName: agentName(aid, agents),
        message: `Credential harvested from ${agentName(aid, agents)}: ${payload?.username || 'unknown'}`,
      }

    case 'finding':
      return {
        id, type, ts,
        icon: Bug,
        color: 'text-orange-400',
        message: `Finding: ${payload?.title || 'unknown'} (${payload?.severity || 'unknown'})`,
      }

    case 'task_created':
      return {
        id, type, ts,
        icon: Activity,
        color: 'text-sky-400',
        agentName: agentName(aid, agents),
        message: `Task queued: ${payload?.module || 'task'} › ${payload?.action || 'run'} → ${agentName(aid, agents)}`,
      }

    case 'report':
      return {
        id, type, ts,
        icon: FileText,
        color: 'text-sky-400',
        message: `Report ${payload?.status || 'queued'}: ${payload?.report_id?.slice(0, 8) || 'unknown'}`,
      }

    default:
      return {
        id, type, ts,
        icon: Bell,
        color: 'text-base-content/40',
        message: `${type}: ${typeof payload === 'string' ? payload.slice(0, 80) : JSON.stringify(payload).slice(0, 80)}`,
      }
  }
}
