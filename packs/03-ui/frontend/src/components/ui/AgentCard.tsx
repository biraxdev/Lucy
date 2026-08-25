import { motion } from 'framer-motion'
import { clsx } from 'clsx'
import { Wifi, HardDrive, User, Clock, ArrowRight, Activity, Cpu } from 'lucide-react'
import { Card, CardBody } from './Card'
import { StatusBadge } from './StatusBadge'
import { getStatusStyle } from '../../lib/statusTheme'
import type { Agent } from '../../types/agent'

const OS_ICON: Record<string, string> = {
  windows: '🪟',
  linux: '🐧',
  darwin: '🍎',
}

export function AgentCard({ agent, onClick }: { agent: Agent; onClick?: () => void }) {
  const lastSeen = agent.last_seen ? new Date(agent.last_seen).toLocaleString() : '—'
  const isOnline = agent.status === 'online'
  const isIdle = agent.status === 'idle'
  const style = getStatusStyle(agent.status)

  // RAM usage percentage
  const ramPct = agent.ram_total && agent.ram_available
    ? Math.round(((agent.ram_total - agent.ram_available) / agent.ram_total) * 100)
    : null

  return (
    <Card onClick={onClick} className="h-full group" hover glow={isOnline}>
      <CardBody className="flex flex-col h-full p-5">
        {/* Header: OS icon + hostname + status */}
        <div className="flex items-start justify-between mb-3">
          <div className="flex items-center gap-3">
            {/* OS icon with glow ring for online agents */}
            <div className={clsx(
              'relative w-10 h-10 rounded-xl flex items-center justify-center text-lg transition-all',
              isOnline ? 'bg-emerald-500/10' : isIdle ? 'bg-amber-500/10' : 'bg-base-300',
              isOnline && 'animate-glow-ring',
            )}>
              {OS_ICON[(agent.os || '').toLowerCase()] ?? '🖥️'}
              {/* Status dot in corner */}
              <span className={clsx(
                'absolute -top-0.5 -right-0.5 w-2.5 h-2.5 rounded-full border-2 border-base-200',
                style.dot,
                (isOnline || isIdle) && 'animate-pulse-soft',
              )} />
            </div>
            <div>
              <h3 className="font-bold text-sm leading-tight group-hover:text-success transition-colors">
                {agent.hostname}
              </h3>
              <p className="text-[10px] text-base-content/50 font-mono mt-0.5">
                {agent.ip_public || agent.ip_private || 'no ip'}
              </p>
            </div>
          </div>
          <StatusBadge status={agent.status} size="sm" />
        </div>

        {/* Metrics grid */}
        <div className="grid grid-cols-2 gap-2 mt-auto">
          <MiniMetric icon={User} label="User" value={agent.username || '—'} />
          <MiniMetric icon={Cpu} label="Arch" value={agent.architecture || '—'} />
          <MiniMetric icon={Wifi} label="Network" value={agent.ip_private || '—'} />
          <MiniMetric icon={Clock} label="Seen" value={lastSeen} />
        </div>

        {/* RAM bar (if available) */}
        {ramPct !== null && (
          <div className="mt-3">
            <div className="flex items-center justify-between text-[9px] text-base-content/40 mb-1">
              <span className="flex items-center gap-1"><HardDrive size={9} /> RAM</span>
              <span className={clsx('font-mono', ramPct > 80 ? 'text-rose-400' : ramPct > 60 ? 'text-amber-400' : 'text-emerald-400')}>
                {ramPct}%
              </span>
            </div>
            <div className="h-1 rounded-full bg-base-300 overflow-hidden">
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: `${ramPct}%` }}
                transition={{ duration: 0.6, ease: 'easeOut' }}
                className={clsx(
                  'h-full rounded-full bg-gradient-to-r',
                  ramPct > 80
                    ? 'from-rose-500 to-rose-400'
                    : ramPct > 60
                    ? 'from-amber-500 to-amber-400'
                    : 'from-emerald-500 to-emerald-400',
                )}
              />
            </div>
          </div>
        )}

        {/* Footer: view details hint */}
        {onClick && (
          <div className="flex items-center gap-1 mt-3 pt-3 border-t border-base-300/50 text-[10px] text-base-content/40 group-hover:text-success transition-colors">
            {isOnline && <Activity size={10} className="text-emerald-400 animate-pulse" />}
            <span className="uppercase tracking-wider font-semibold">View details</span>
            <ArrowRight size={11} className="group-hover:translate-x-1 transition-transform" />
          </div>
        )}
      </CardBody>
    </Card>
  )
}

function MiniMetric({ icon: Icon, label, value }: { icon: React.ElementType; label: string; value: string }) {
  return (
    <div className="flex items-center gap-2 p-2 rounded-lg bg-base-300/50">
      <Icon size={12} className="text-base-content/40 shrink-0" />
      <div className="min-w-0">
        <p className="text-[9px] uppercase tracking-wider text-base-content/40">{label}</p>
        <p className="text-[11px] text-base-content/80 truncate font-mono">{value}</p>
      </div>
    </div>
  )
}
