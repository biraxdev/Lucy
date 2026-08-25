import { useState, useRef, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Play, CheckCircle2, AlertCircle, Loader2, ChevronRight,
  ArrowLeft, Rocket, Zap, Eye, KeyRound, Anchor, Network, ShieldAlert,
  Download, GitBranch, TerminalSquare, RotateCcw,
} from 'lucide-react'
import { type Mission } from './missions'
import { executeMission, type MissionStepResult, type MissionSummary } from '../../api/copilot'
import { useCopilotStore } from '../../stores/copilotStore'

const ICONS: Record<string, any> = {
  Rocket, Zap, Eye, KeyRound, Anchor, Network, ShieldAlert, Download, GitBranch, TerminalSquare,
}

interface StepState {
  index: number
  label: string
  insight: string
  module: string
  action: string
  status: 'pending' | 'running' | 'completed' | 'ok' | 'failed' | 'error'
  result?: unknown
  error?: string
  taskId?: string
}

interface Props {
  mission: Mission
  agentId: string
  onBack: () => void
  onChatAsk: (question: string) => void
}

export function MissionRunner({ mission, agentId, onBack, onChatAsk }: Props) {
  const [steps, setSteps] = useState<StepState[]>(
    mission.steps.map((s, i) => ({
      index: i,
      label: s.label,
      insight: s.insight,
      module: s.module,
      action: s.action,
      status: 'pending',
    }))
  )
  const [running, setRunning] = useState(false)
  const [done, setDone] = useState(false)
  const [summary, setSummary] = useState<MissionSummary | null>(null)
  const [expandedStep, setExpandedStep] = useState<number | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const { openWithMessage } = useCopilotStore()

  const scrollToBottom = useCallback(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [])

  useEffect(() => {
    scrollToBottom()
  }, [steps, scrollToBottom])

  const run = async () => {
    setRunning(true)
    setDone(false)
    setSummary(null)
    setSteps((prev) => prev.map((s) => ({ ...s, status: 'pending', result: undefined, error: undefined })))

    try {
      const gen = executeMission(
        mission.id,
        agentId,
        mission.steps.map((s) => ({
          module: s.module,
          action: s.action,
          params: s.params,
          label: s.label,
          insight: s.insight,
          timeout: s.timeout,
        })),
        mission.title
      )

      for await (const event of gen) {
        if (event.type === 'mission_start') {
          // Nothing special, just continue
        } else if (event.type === 'step_start') {
          setSteps((prev) => prev.map((s, i) =>
            i === event.step - 1 ? { ...s, status: 'running' } : s
          ))
          setExpandedStep(event.step - 1)
        } else if (event.type === 'step_done') {
          setSteps((prev) => prev.map((s, i) =>
            i === event.step - 1
              ? { ...s, status: event.status as StepState['status'], result: event.result, error: event.error, taskId: event.task_id }
              : s
          ))
        } else if (event.type === 'step_error') {
          setSteps((prev) => prev.map((s, i) =>
            i === event.step - 1 ? { ...s, status: 'error', error: event.error } : s
          ))
        } else if (event.type === 'mission_done') {
          setSummary(event)
          setDone(true)
        }
      }
    } catch (err: any) {
      setSummary({
        type: 'mission_done',
        mission_id: mission.id,
        title: mission.title,
        total_steps: mission.steps.length,
        completed: 0,
        failed: mission.steps.length,
        agent_id: agentId,
      })
      setDone(true)
    } finally {
      setRunning(false)
    }
  }

  // Auto-start on mount
  useEffect(() => {
    run()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const Icon = ICONS[mission.icon] || Rocket
  const completedCount = steps.filter((s) => s.status === 'completed' || s.status === 'ok').length
  const failedCount = steps.filter((s) => s.status === 'failed' || s.status === 'error').length
  const progress = steps.length > 0 ? ((completedCount + failedCount) / steps.length) * 100 : 0

  const renderResult = (step: StepState) => {
    if (!step.result && !step.error) return null

    const resultStr = step.result
      ? (typeof step.result === 'string' ? step.result : JSON.stringify(step.result, null, 2))
      : ''
    const errorStr = step.error || ''

    return (
      <div className="mt-1.5 space-y-1">
        {errorStr && (
          <div className="text-[10px] text-error font-mono bg-error/10 rounded p-1.5">
            {errorStr}
          </div>
        )}
        {resultStr && (
          <pre className="text-[10px] text-base-content/60 font-mono bg-base-300/50 rounded p-1.5 max-h-40 overflow-y-auto scrollbar-thin whitespace-pre-wrap break-all">
            {resultStr.length > 800 ? resultStr.substring(0, 800) + '\n... (' + resultStr.length + ' chars total)' : resultStr}
          </pre>
        )}
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full min-h-0">
      {/* Header */}
      <div className="shrink-0 p-2.5 border-b border-base-300 space-y-2">
        <div className="flex items-center gap-2">
          <button
            className="btn btn-xs btn-ghost btn-square"
            onClick={onBack}
            disabled={running}
          >
            <ArrowLeft size={14} />
          </button>
          <div className="shrink-0 w-8 h-8 rounded-lg bg-success/10 flex items-center justify-center">
            <Icon size={14} className="text-success" />
          </div>
          <div className="flex-1 min-w-0">
            <h2 className="text-sm font-bold truncate">{mission.title}</h2>
            <p className="text-[10px] text-base-content/40 truncate">{mission.description}</p>
          </div>
        </div>

        {/* Progress bar */}
        <div className="space-y-1">
          <div className="flex items-center justify-between text-[10px] text-base-content/50">
            <span>{completedCount + failedCount} / {steps.length} étapes</span>
            <span>
              {completedCount > 0 && <span className="text-success">{completedCount} OK</span>}
              {failedCount > 0 && <span className="text-error ml-1">{failedCount} échec</span>}
            </span>
          </div>
          <progress
            className={`progress w-full ${failedCount > 0 ? 'progress-warning' : 'progress-success'}`}
            value={progress}
            max="100"
          />
        </div>
      </div>

      {/* Steps */}
      <div className="flex-1 overflow-y-auto p-2 space-y-1.5 min-h-0 scrollbar-thin">
        <AnimatePresence>
          {steps.map((step, i) => {
            const isExpanded = expandedStep === i
            const isRunning = step.status === 'running'
            return (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                className={`rounded-lg border transition-all ${
                  step.status === 'completed' ? 'border-success/20 bg-success/5' :
                  step.status === 'failed' || step.status === 'error' ? 'border-error/20 bg-error/5' :
                  isRunning ? 'border-info/30 bg-info/5' :
                  'border-base-300/30 bg-base-300/20'
                }`}
              >
                <div
                  className="p-2 cursor-pointer flex items-center gap-2"
                  onClick={() => setExpandedStep(isExpanded ? null : i)}
                >
                  {/* Status icon */}
                  <div className="shrink-0 w-6 h-6 rounded-full flex items-center justify-center">
                    {step.status === 'completed' ? (
                      <CheckCircle2 size={16} className="text-success" />
                    ) : step.status === 'failed' || step.status === 'error' ? (
                      <AlertCircle size={16} className="text-error" />
                    ) : isRunning ? (
                      <Loader2 size={16} className="animate-spin text-info" />
                    ) : (
                      <div className="w-4 h-4 rounded-full border-2 border-base-content/20" />
                    )}
                  </div>

                  {/* Step number + module */}
                  <div className="shrink-0 w-5 h-5 rounded bg-base-300/50 flex items-center justify-center text-[9px] font-mono font-bold text-base-content/40">
                    {i + 1}
                  </div>

                  {/* Label */}
                  <div className="flex-1 min-w-0">
                    <div className="text-xs font-medium truncate">{step.label}</div>
                    <div className="text-[9px] text-base-content/30 font-mono truncate">
                      {step.module}/{step.action}
                    </div>
                  </div>

                  {/* Expand chevron */}
                  {(step.result || step.error) && (
                    <ChevronRight
                      size={12}
                      className={`text-base-content/30 transition-transform ${isExpanded ? 'rotate-90' : ''}`}
                    />
                  )}
                </div>

                {/* Insight (when completed) */}
                {step.status === 'completed' && step.insight && !isExpanded && (
                  <div className="px-2 pb-1.5 pl-10 text-[10px] text-success/70 italic">
                    → {step.insight}
                  </div>
                )}

                {/* Expanded result */}
                <AnimatePresence>
                  {isExpanded && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: 'auto', opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      className="overflow-hidden"
                    >
                      <div className="px-2 pb-2 pl-10">
                        {step.insight && (
                          <div className="text-[10px] text-base-content/50 mb-1">
                            <span className="text-success font-medium">Insight: </span>
                            {step.insight}
                          </div>
                        )}
                        {renderResult(step)}
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </motion.div>
            )
          })}
        </AnimatePresence>
        <div ref={bottomRef} />
      </div>

      {/* Footer — summary + actions */}
      <div className="shrink-0 p-2.5 border-t border-base-300 space-y-2">
        {done && summary && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className={`rounded-lg p-2 text-center ${
              (summary.failed ?? 0) === 0 ? 'bg-success/10 text-success' :
              (summary.completed ?? 0) > 0 ? 'bg-warning/10 text-warning' :
              'bg-error/10 text-error'
            }`}
          >
            <div className="text-sm font-bold">
              {(summary.failed ?? 0) === 0 ? 'Mission accomplie!' :
               (summary.completed ?? 0) > 0 ? `Mission partielle: ${summary.completed}/${summary.total_steps}` :
               'Mission échouée'}
            </div>
            <div className="text-[10px] opacity-70">
              {summary.completed} réussies · {summary.failed} échouées · {summary.total_steps} total
            </div>
          </motion.div>
        )}

        <div className="flex gap-1.5">
          {done ? (
            <>
              <button
                className="btn btn-sm btn-outline flex-1 gap-1"
                onClick={() => run()}
              >
                <RotateCcw size={12} /> Relancer
              </button>
              <button
                className="btn btn-sm btn-success flex-1 gap-1"
                onClick={() => onBack()}
              >
                <Rocket size={12} /> Autres missions
              </button>
            </>
          ) : (
            <button
              className="btn btn-sm btn-ghost flex-1 gap-1"
              onClick={() => openWithMessage(
                `J'exécute la mission "${mission.title}" sur l'agent. Analyse les résultats et dis-moi ce que tu trouves.`
              )}
              disabled={running}
            >
              <Zap size={12} /> Analyser avec l'IA
            </button>
          )}
        </div>

        {/* Suggested next missions */}
        {done && mission.suggests && mission.suggests.length > 0 && (
          <div className="pt-1">
            <div className="text-[10px] uppercase tracking-wider text-base-content/40 font-semibold mb-1">
              Prochaines étapes
            </div>
            <div className="flex gap-1 flex-wrap">
              {mission.suggests.slice(0, 4).map((id) => (
                <button
                  key={id}
                  className="badge badge-xs badge-ghost cursor-pointer hover:badge-success text-[10px]"
                  onClick={() => onChatAsk(`Lance la mission ${id}`)}
                >
                  {id}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
