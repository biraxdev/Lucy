import { clsx } from 'clsx'
import { getStatusStyle } from '../../lib/statusTheme'

type Status = 'online' | 'offline' | 'idle' | 'running' | 'queued' | 'completed' | 'failed' | 'cancelled' | 'pending' | string

export function StatusBadge({ status, label, size = 'md' }: { status: Status; label?: string; size?: 'sm' | 'md' }) {
  const style = getStatusStyle(status)
  const sizeCls = size === 'sm' ? 'px-2 py-0.5 text-[9px]' : 'px-2.5 py-1 text-[11px]'

  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1.5 rounded-full font-semibold uppercase tracking-wide border',
        style.text,
        style.bg,
        style.border,
        sizeCls,
        style.animation,
      )}
    >
      {/* Status dot with ping for active states */}
      <span className="relative flex items-center justify-center">
        <span className={clsx('w-1.5 h-1.5 rounded-full', style.dot)} />
        {(status === 'online' || status === 'running') && (
          <span className={clsx('absolute w-1.5 h-1.5 rounded-full animate-dot-ping', style.dot)} />
        )}
      </span>
      {label ?? style.label}
    </span>
  )
}
