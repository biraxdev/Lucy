import { motion } from 'framer-motion'
import { clsx } from 'clsx'

type SemanticColor = 'success' | 'warning' | 'info' | 'error' | 'ghost'

interface QuickActionProps {
  icon: React.ElementType
  label: string
  description?: string
  color?: SemanticColor
  onClick: () => void
}

const colorMap: Record<SemanticColor, string> = {
  success: 'border-emerald-500/20 bg-emerald-500/5 text-emerald-400 hover:bg-emerald-500/10 hover:border-emerald-500/40',
  warning: 'border-amber-500/20 bg-amber-500/5 text-amber-400 hover:bg-amber-500/10 hover:border-amber-500/40',
  info:    'border-sky-500/20 bg-sky-500/5 text-sky-400 hover:bg-sky-500/10 hover:border-sky-500/40',
  error:   'border-rose-500/20 bg-rose-500/5 text-rose-400 hover:bg-rose-500/10 hover:border-rose-500/40',
  ghost:   'border-base-content/10 bg-base-200 text-base-content/70 hover:bg-base-300 hover:border-base-content/20',
}

const iconBgMap: Record<SemanticColor, string> = {
  success: 'bg-emerald-500/10',
  warning: 'bg-amber-500/10',
  info:    'bg-sky-500/10',
  error:   'bg-rose-500/10',
  ghost:   'bg-base-100/50',
}

export function QuickAction({ icon: Icon, label, description, color = 'ghost', onClick }: QuickActionProps) {
  return (
    <motion.button
      whileHover={{ y: -3, transition: { duration: 0.15 } }}
      whileTap={{ scale: 0.97 }}
      onClick={onClick}
      className={clsx(
        'flex items-center gap-3 p-3 rounded-xl border text-left transition-all duration-200 w-full',
        colorMap[color],
      )}
    >
      <div className={clsx('p-2 rounded-lg transition-colors', iconBgMap[color])}>
        <Icon size={18} />
      </div>
      <div className="min-w-0">
        <p className="font-semibold text-sm">{label}</p>
        {description && <p className="text-[10px] text-current/70 truncate">{description}</p>}
      </div>
    </motion.button>
  )
}
