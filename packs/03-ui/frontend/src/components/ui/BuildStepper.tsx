import { motion, AnimatePresence } from 'framer-motion'
import { CheckCircle2, Loader2, Circle, Package, Cpu, Download } from 'lucide-react'

export interface BuildStep {
  key: string
  label: string
}

const DEFAULT_STEPS: BuildStep[] = [
  { key: 'queued',    label: 'Queued' },
  { key: 'building',  label: 'Compiling' },
  { key: 'packaging', label: 'Packaging' },
  { key: 'done',      label: 'Ready' },
]

const STEP_ICONS: Record<string, React.ElementType> = {
  queued: Circle,
  building: Cpu,
  packaging: Package,
  done: Download,
}

const STEP_ORDER: Record<string, number> = {
  idle: -1,
  queued: 0,
  building: 1,
  packaging: 2,
  done: 3,
  error: 3,
}

export function BuildStepper({ status, steps = DEFAULT_STEPS }: { status: string; steps?: BuildStep[] }) {
  const currentIdx = STEP_ORDER[status] ?? -1
  const isError = status === 'error'

  return (
    <div className="flex items-center justify-between relative px-2">
      {/* Background line */}
      <div className="absolute top-5 left-4 right-4 h-0.5 bg-base-300 -z-0" />
      {/* Progress fill */}
      <motion.div
        className="absolute top-5 left-4 h-0.5 bg-success -z-0"
        initial={{ width: 0 }}
        animate={{ width: currentIdx >= 0 ? `${(currentIdx / (steps.length - 1)) * 100}%` : '0%' }}
        transition={{ duration: 0.5, ease: 'easeOut' }}
        style={{ maxWidth: 'calc(100% - 2rem)' }}
      />
      {steps.map((step, i) => {
        const reached = i <= currentIdx && !isError
        const isCurrent = i === currentIdx && status !== 'done' && !isError
        const isDone = i < currentIdx || (i === currentIdx && status === 'done')
        const Icon = isDone ? CheckCircle2 : isCurrent ? Loader2 : STEP_ICONS[step.key] || Circle
        return (
          <div key={step.key} className="flex flex-col items-center gap-2 relative z-10 flex-1">
            <motion.div
              initial={{ scale: 0.8 }}
              animate={{ scale: 1 }}
              transition={{ delay: i * 0.1 }}
              className={`w-10 h-10 rounded-full flex items-center justify-center border-2 transition-colors ${
                isDone
                  ? 'bg-success border-success text-base-100'
                  : isCurrent
                  ? 'bg-success/15 border-success text-success'
                  : reached
                  ? 'bg-success/10 border-success/40 text-success'
                  : 'bg-base-200 border-base-300 text-base-content/30'
              }`}
            >
              <Icon size={18} className={isCurrent ? 'animate-spin' : ''} />
            </motion.div>
            <span className={`text-[11px] font-medium ${reached || isCurrent ? 'text-base-content' : 'text-base-content/40'}`}>
              {step.label}
            </span>
          </div>
        )
      })}
    </div>
  )
}
