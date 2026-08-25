import { motion } from 'framer-motion'
import { clsx, type ClassValue } from 'clsx'

interface CardProps {
  children: React.ReactNode
  className?: ClassValue
  hover?: boolean
  glow?: boolean
  onClick?: () => void
}

export function Card({ children, className, hover = true, glow = false, onClick }: CardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, ease: 'easeOut' }}
      whileHover={hover ? { y: -4, transition: { duration: 0.15 } } : undefined}
      whileTap={onClick ? { scale: 0.98 } : undefined}
      onClick={onClick}
      className={clsx(
        'relative rounded-2xl bg-base-200 border border-base-300 overflow-hidden',
        hover && 'cursor-pointer group',
        glow && 'shadow-lg shadow-success/5',
        onClick && 'cursor-pointer',
        className
      )}
    >
      {hover && (
        <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none bg-gradient-to-br from-success/5 to-transparent" />
      )}
      <div className="relative z-10 h-full">{children}</div>
    </motion.div>
  )
}

export function CardHeader({ children, className }: { children: React.ReactNode; className?: ClassValue }) {
  return <div className={clsx('px-5 pt-5 pb-2 flex items-center justify-between', className)}>{children}</div>
}

export function CardBody({ children, className }: { children: React.ReactNode; className?: ClassValue }) {
  return <div className={clsx('px-5 pb-5', className)}>{children}</div>
}

export function CardMetric({ value, label, trend, color = 'text-success', pulse = false }: {
  value: string | number
  label: string
  trend?: string
  color?: string
  pulse?: boolean
}) {
  return (
    <div>
      <p className={clsx('text-3xl font-bold tracking-tight tabular-nums', color, pulse && 'animate-pulse-soft')}>{value}</p>
      <p className="text-xs text-base-content/60 mt-0.5 font-medium uppercase tracking-wider">{label}</p>
      {trend && <p className="text-[10px] text-base-content/40 mt-1">{trend}</p>}
    </div>
  )
}
