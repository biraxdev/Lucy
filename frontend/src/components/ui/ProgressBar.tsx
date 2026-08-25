import { motion } from 'framer-motion'
import { clsx } from 'clsx'
import { getStatusStyle } from '../../lib/statusTheme'

interface ProgressBarProps {
  /** 0-100, or undefined for indeterminate */
  value?: number
  /** Status string to derive color from (online, running, failed, etc.) */
  status?: string
  /** Height in tailwind units */
  height?: 'xs' | 'sm' | 'md'
  /** Show animated shimmer on the fill */
  shimmer?: boolean
  /** Show the percentage label */
  showLabel?: boolean
  className?: string
}

export function ProgressBar({
  value,
  status = 'running',
  height = 'sm',
  shimmer = false,
  showLabel = false,
  className,
}: ProgressBarProps) {
  const style = getStatusStyle(status)
  const heightCls = height === 'xs' ? 'h-1' : height === 'md' ? 'h-3' : 'h-1.5'
  const isIndeterminate = value === undefined || value === null

  return (
    <div className={clsx('w-full', className)}>
      <div className={clsx('relative w-full rounded-full bg-base-300 overflow-hidden', heightCls)}>
        {isIndeterminate ? (
          // Indeterminate sweep
          <div
            className={clsx('absolute inset-y-0 left-0 w-1/4 rounded-full bg-gradient-to-r', style.fill, 'animate-progress-sweep')}
          />
        ) : (
          <motion.div
            initial={{ width: 0 }}
            animate={{ width: `${Math.min(100, Math.max(0, value))}%` }}
            transition={{ duration: 0.5, ease: 'easeOut' }}
            className={clsx(
              'absolute inset-y-0 left-0 rounded-full bg-gradient-to-r',
              style.fill,
              shimmer && 'animate-fill-shimmer',
            )}
          />
        )}
      </div>
      {showLabel && !isIndeterminate && (
        <div className={clsx('text-[10px] font-mono mt-0.5 text-right', style.text)}>
          {Math.round(value!)}%
        </div>
      )}
    </div>
  )
}
