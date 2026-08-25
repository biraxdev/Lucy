import { useState } from 'react'
import { Plus, Play, Save, Trash2, GripVertical, ChevronDown, ChevronUp, Download, BookOpen, Zap, Clock, MousePointer } from 'lucide-react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getTimelines, createTimeline, updateTimeline, executeTimeline, deleteTimeline, getTemplates, importTemplate } from '../api/tasks'
import { getModules } from '../api/modules'
import { listGroups } from '../api/groups'
import type { Timeline, TimelineStep } from '../types/task'

const EMPTY_STEP: TimelineStep = { order: 1, module: 'info', action: 'run', params: {}, delay: 0, timeout: 60, priority: 'normal' }

const CAT_COLOR: Record<string, string> = {
  recon: 'badge-info', credentials: 'badge-warning', persistence: 'badge-ghost',
  lateral: 'badge-primary', exfil: 'badge-error', surveillance: 'badge-secondary',
  simulation: 'badge-accent', full: 'badge-error',
}
const CAT_BAR: Record<string, string> = {
  recon: 'bg-blue-500', credentials: 'bg-yellow-500', persistence: 'bg-purple-500',
  lateral: 'bg-cyan-500', exfil: 'bg-orange-500', surveillance: 'bg-pink-500',
  simulation: 'bg-green-500', full: 'bg-red-600',
}

function TemplateList({ templates, onImport, importing }: {
  templates: any[]
  onImport: (id: string) => void
  importing: boolean
}) {
  const [expanded, setExpanded] = useState<string | null>(null)

  return (
    <div className="space-y-2">
      {templates.map((tpl: any) => {
        const isOpen = expanded === tpl.id
        const critCount = tpl.steps.filter((s: any) => s.priority === 'critical').length
        const highCount = tpl.steps.filter((s: any) => s.priority === 'high').length
        const modules = [...new Set(tpl.steps.map((s: any) => s.module))] as string[]
        const phases = tpl.phases as { label: string; steps: number[] }[] | undefined
        return (
          <div key={tpl.id} className="border border-base-300 rounded-xl overflow-hidden hover:border-base-content/20 transition-colors">
            {/* Header row — always visible */}
            <div
              className="flex items-center gap-3 px-4 py-3 cursor-pointer bg-base-200 hover:bg-base-300 transition-colors select-none"
              onClick={() => setExpanded(isOpen ? null : tpl.id)}
            >
              <span className="text-xl shrink-0">{tpl.icon}</span>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-bold text-sm">{tpl.name}</span>
                  <span className={`badge badge-xs ${CAT_COLOR[tpl.category] ?? 'badge-ghost'}`}>{tpl.category}</span>
                  <span className="badge badge-xs badge-ghost">{tpl.steps.length} étapes</span>
                  {tpl.trigger === 'on_connect' && <span className="badge badge-xs badge-success">auto</span>}
                </div>
                <p className="text-xs text-base-content/50 truncate mt-0.5">{tpl.description}</p>
              </div>
              <div className="flex items-center gap-3 shrink-0">
                {critCount > 0 && <span className="text-xs text-red-400 font-mono">{critCount}×critical</span>}
                {highCount > 0 && <span className="text-xs text-yellow-400 font-mono">{highCount}×high</span>}
                <span className="text-base-content/30 text-sm">{isOpen ? '▲' : '▼'}</span>
              </div>
            </div>

            {/* Expanded detail */}
            {isOpen && (
              <div className="px-4 py-3 bg-base-100 space-y-3 border-t border-base-300">
                <p className="text-xs text-base-content/60 leading-relaxed">{tpl.description}</p>

                {/* Phase breakdown */}
                {phases && phases.length > 0 && (
                  <div>
                    <p className="text-xs font-semibold text-base-content/50 mb-1.5 uppercase tracking-wide">Phases</p>
                    <div className="flex gap-1 flex-wrap">
                      {phases.map((ph: any, i: number) => (
                        <div key={i} className="flex items-center gap-1 bg-base-200 rounded px-2 py-1">
                          <div className={`w-2 h-2 rounded-full ${CAT_BAR[tpl.category] ?? 'bg-gray-500'} shrink-0`} />
                          <span className="text-xs font-medium">{ph.label}</span>
                          <span className="text-xs text-base-content/40">({ph.steps.length} étapes)</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Step timeline */}
                <div>
                  <p className="text-xs font-semibold text-base-content/50 mb-1.5 uppercase tracking-wide">Séquence complète</p>
                  <div className="space-y-0.5 max-h-52 overflow-y-auto scrollbar-thin pr-1">
                    {tpl.steps.map((s: any, i: number) => (
                      <div key={i} className="flex items-center gap-2 py-0.5">
                        <span className={`w-5 h-5 rounded text-[9px] flex items-center justify-center font-mono shrink-0 ${
                          s.priority === 'critical' ? 'bg-red-600 text-white' :
                          s.priority === 'high'     ? 'bg-orange-500 text-white' :
                          s.priority === 'normal'   ? 'bg-base-300 text-base-content/60' :
                          'bg-base-300/40 text-base-content/30'
                        }`}>{i + 1}</span>
                        <span className="font-mono text-xs text-success">{s.module}</span>
                        <span className="text-xs text-base-content/40">:{s.action}</span>
                        {Object.keys(s.params).length > 0 && (
                          <span className="text-[10px] text-base-content/30 truncate max-w-xs">{JSON.stringify(s.params)}</span>
                        )}
                        {s.delay > 0 && <span className="ml-auto text-[10px] text-base-content/30 shrink-0">+{s.delay}s</span>}
                      </div>
                    ))}
                  </div>
                </div>

                {/* Modules */}
                <div className="flex flex-wrap gap-1">
                  {modules.map((m: string) => (
                    <span key={m} className="badge badge-xs badge-outline font-mono">{m}</span>
                  ))}
                </div>

                <button
                  className="btn btn-sm btn-success w-full gap-1"
                  disabled={importing}
                  onClick={() => onImport(tpl.id)}
                >
                  <Download size={13} /> Importer dans Timeline Builder
                </button>
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

function StepBlock({
  step, index, total, onChange, onRemove, onMove,
}: {
  step: TimelineStep; index: number; total: number
  onChange: (s: TimelineStep) => void
  onRemove: () => void
  onMove: (dir: -1 | 1) => void
}) {
  const [open, setOpen] = useState(false)
  return (
    <div className="card bg-base-300 border border-base-content/10">
      <div className="flex items-center gap-2 p-3">
        <GripVertical size={14} className="text-base-content/30 shrink-0" />
        <span className="badge badge-sm badge-ghost">{index + 1}</span>
        <input
          className="input input-xs input-bordered w-32 font-mono"
          value={step.module}
          onChange={(e) => onChange({ ...step, module: e.target.value })}
          placeholder="module"
        />
        <input
          className="input input-xs input-bordered w-24"
          value={step.action}
          onChange={(e) => onChange({ ...step, action: e.target.value })}
          placeholder="action"
        />
        <span className="text-xs text-base-content/40">delay:</span>
        <input
          className="input input-xs input-bordered w-16"
          type="number" min={0}
          value={step.delay}
          onChange={(e) => onChange({ ...step, delay: Number(e.target.value) })}
        />
        <span className="text-xs text-base-content/40">s</span>
        <div className="flex-1" />
        <button className="btn btn-xs btn-ghost" onClick={() => onMove(-1)} disabled={index === 0}><ChevronUp size={12} /></button>
        <button className="btn btn-xs btn-ghost" onClick={() => onMove(1)} disabled={index === total - 1}><ChevronDown size={12} /></button>
        <button className="btn btn-xs btn-ghost" onClick={() => setOpen((v) => !v)}>Params</button>
        <button className="btn btn-xs btn-ghost text-error" onClick={onRemove}><Trash2 size={12} /></button>
      </div>
      {open && (
        <div className="px-3 pb-3">
          <textarea
            className="textarea textarea-bordered w-full font-mono text-xs"
            rows={3}
            value={JSON.stringify(step.params, null, 2)}
            onChange={(e) => {
              try { onChange({ ...step, params: JSON.parse(e.target.value) }) } catch {}
            }}
          />
          <div className="flex gap-2 mt-2">
            <label className="text-xs">timeout(s)
              <input className="input input-xs input-bordered w-16 ml-1" type="number" value={step.timeout}
                onChange={(e) => onChange({ ...step, timeout: Number(e.target.value) })} />
            </label>
            <label className="text-xs">priority
              <select className="select select-xs select-bordered ml-1" value={step.priority}
                onChange={(e) => onChange({ ...step, priority: e.target.value as any })}>
                {['critical', 'high', 'normal', 'low'].map((p) => <option key={p}>{p}</option>)}
              </select>
            </label>
          </div>
        </div>
      )}
    </div>
  )
}

export default function TimelineBuilder() {
  const qc = useQueryClient()
  const { data: timelines = [] } = useQuery({ queryKey: ['timelines'], queryFn: getTimelines })
  const { data: modules = [] } = useQuery({ queryKey: ['modules'], queryFn: getModules })
  const createMut = useMutation({ mutationFn: createTimeline, onSuccess: () => qc.invalidateQueries({ queryKey: ['timelines'] }) })
  const updateMut = useMutation({ mutationFn: ({ id, data }: { id: string; data: Partial<Timeline> }) => updateTimeline(id, data), onSuccess: () => qc.invalidateQueries({ queryKey: ['timelines'] }) })
  const execMut   = useMutation({ mutationFn: (id: string) => executeTimeline(id) })
  const deleteMut = useMutation({ mutationFn: deleteTimeline, onSuccess: () => qc.invalidateQueries({ queryKey: ['timelines'] }) })

  const [selected, setSelected] = useState<Timeline | null>(null)
  const [steps, setSteps] = useState<TimelineStep[]>([])
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [trigger, setTrigger] = useState('manual')
  const [cronExpr, setCronExpr] = useState('0 * * * *')
  const [agentGroup, setAgentGroup] = useState<string[]>(['all'])
  const [tlStatus, setTlStatus] = useState<'draft' | 'active'>('draft')
  const [moduleSearch, setModuleSearch] = useState('')
  const [execResult, setExecResult] = useState<string | null>(null)
  const [showTemplates, setShowTemplates] = useState(false)

  const { data: groups = [] } = useQuery({ queryKey: ['groups'], queryFn: listGroups })

  const { data: templates = [] } = useQuery({ queryKey: ['timeline-templates'], queryFn: getTemplates })
  const importMut = useMutation({
    mutationFn: (id: string) => importTemplate(id),
    onSuccess: (tl) => {
      qc.invalidateQueries({ queryKey: ['timelines'] })
      selectTimeline(tl)
      setShowTemplates(false)
    },
  })

  const selectTimeline = (tl: Timeline) => {
    setSelected(tl)
    setName(tl.name)
    setDescription(tl.description)
    setSteps(tl.steps)
    const rawTrigger = tl.trigger || 'manual'
    if (rawTrigger.startsWith('schedule(')) {
      setTrigger('schedule')
      setCronExpr(rawTrigger.replace('schedule(', '').replace(')', ''))
    } else {
      setTrigger(rawTrigger)
    }
    setAgentGroup(tl.agent_group)
    setTlStatus((tl.status as any) === 'active' ? 'active' : 'draft')
  }

  const newTimeline = () => {
    setSelected(null)
    setName('New Timeline')
    setDescription('')
    setSteps([{ ...EMPTY_STEP }])
    setTrigger('manual')
    setCronExpr('0 * * * *')
    setAgentGroup(['all'])
    setTlStatus('draft')
  }

  const addStep = (module = 'info') => {
    setSteps((s) => [...s, { ...EMPTY_STEP, module, order: s.length + 1 }])
  }

  const updateStep = (i: number, s: TimelineStep) => {
    setSteps((prev) => prev.map((x, idx) => (idx === i ? s : x)))
  }

  const removeStep = (i: number) => setSteps((s) => s.filter((_, idx) => idx !== i))

  const moveStep = (i: number, dir: -1 | 1) => {
    const arr = [...steps]
    const j = i + dir
    if (j < 0 || j >= arr.length) return
    ;[arr[i], arr[j]] = [arr[j], arr[i]]
    setSteps(arr.map((s, idx) => ({ ...s, order: idx + 1 })))
  }

  const saveTimeline = async () => {
    const effectiveTrigger = trigger === 'schedule' ? `schedule(${cronExpr})` : trigger
    const payload = { name, description, steps, trigger: effectiveTrigger, agent_group: agentGroup, status: tlStatus }
    if (selected) {
      await updateMut.mutateAsync({ id: selected.id, data: payload })
    } else {
      const tl = await createMut.mutateAsync(payload)
      setSelected(tl)
    }
  }

  const execute = async () => {
    if (!selected) return
    try {
      const r = await execMut.mutateAsync(selected.id)
      setExecResult(JSON.stringify(r))
    } catch (e: any) {
      setExecResult(`Error: ${e.message}`)
    }
  }

  const filteredModules = modules.filter((m: any) =>
    m.name.toLowerCase().includes(moduleSearch.toLowerCase())
  )

  return (
    <div className="page-container flex gap-4 h-[calc(100vh-3.5rem)] overflow-hidden">
      {/* Templates modal */}
      {showTemplates && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="bg-base-100 border border-base-300 rounded-2xl shadow-2xl w-full max-w-3xl p-6 overflow-y-auto max-h-[85vh]">
            <div className="flex items-center justify-between mb-5">
              <h2 className="text-xl font-bold flex items-center gap-2"><BookOpen size={20} className="text-success" /> Plans d'attaque préconfigurés</h2>
              <button className="btn btn-sm btn-ghost" onClick={() => setShowTemplates(false)}>✕</button>
            </div>
            <TemplateList templates={templates} onImport={(id) => importMut.mutate(id)} importing={importMut.isPending} />
          </div>
        </div>
      )}

      {/* Left — Timelines list */}
      <aside className="w-56 flex flex-col gap-2 shrink-0 overflow-y-auto scrollbar-thin">
        <div className="flex items-center justify-between">
          <span className="text-sm font-semibold">Timelines</span>
          <div className="flex gap-1">
            <button className="btn btn-xs btn-outline gap-1" onClick={() => setShowTemplates(true)}><BookOpen size={11} /></button>
            <button className="btn btn-xs btn-success gap-1" onClick={newTimeline}><Plus size={12} /> New</button>
          </div>
        </div>
        {timelines.map((tl: Timeline) => (
          <div
            key={tl.id}
            className={`card bg-base-200 p-2 cursor-pointer text-sm hover:bg-base-300 transition-colors ${selected?.id === tl.id ? 'ring-1 ring-success' : ''}`}
            onClick={() => selectTimeline(tl)}
          >
            <p className="font-medium truncate">{tl.name}</p>
            <div className="flex gap-1 mt-1">
              <span className={`badge badge-xs badge-${tl.status === 'active' ? 'success' : tl.status === 'completed' ? 'info' : 'ghost'}`}>{tl.status}</span>
              <span className="badge badge-xs badge-ghost">{tl.steps?.length ?? 0} steps</span>
            </div>
          </div>
        ))}
        {timelines.length === 0 && <p className="text-xs text-base-content/40">No timelines yet</p>}
      </aside>

      {/* Centre — Canvas */}
      <div className="flex-1 overflow-y-auto scrollbar-thin space-y-3">
        {name ? (
          <>
            <div className="flex items-center gap-2">
              <input className="input input-bordered flex-1 font-bold text-lg" value={name} onChange={(e) => setName(e.target.value)} />
              <button className="btn btn-sm btn-outline gap-1" onClick={saveTimeline}><Save size={14} /> Save</button>
              {selected && (
                <>
                  <button className="btn btn-sm btn-success gap-1" onClick={execute}><Play size={14} /> Execute</button>
                  <button className="btn btn-sm btn-error btn-outline gap-1" onClick={() => { deleteMut.mutate(selected.id); setSelected(null) }}><Trash2 size={14} /></button>
                </>
              )}
            </div>

            <input className="input input-bordered w-full input-sm" placeholder="Description…" value={description} onChange={(e) => setDescription(e.target.value)} />

            {/* Trigger + Target + Status row */}
            <div className="bg-base-200 border border-base-300 rounded-xl p-3 space-y-3">
              <div className="flex gap-2 flex-wrap items-center">
                {/* Trigger mode buttons */}
                <span className="text-xs font-semibold text-base-content/50 uppercase">Trigger</span>
                {[
                  { val: 'manual',     label: 'Manual',     icon: <MousePointer size={12} /> },
                  { val: 'on_connect', label: 'On Connect', icon: <Zap size={12} /> },
                  { val: 'schedule',   label: 'Schedule',   icon: <Clock size={12} /> },
                ].map(({ val, label, icon }) => (
                  <button
                    key={val}
                    onClick={() => setTrigger(val)}
                    className={`btn btn-xs gap-1 ${
                      trigger === val ? (
                        val === 'on_connect' ? 'btn-success' :
                        val === 'schedule'   ? 'btn-warning' : 'btn-primary'
                      ) : 'btn-ghost'
                    }`}
                  >
                    {icon} {label}
                  </button>
                ))}

                {/* Trigger hint */}
                {trigger === 'on_connect' && (
                  <span className="text-xs text-green-400 opacity-70">Fires automatically when a matching agent connects</span>
                )}
              </div>

              {/* Cron editor */}
              {trigger === 'schedule' && (
                <div className="space-y-1">
                  <label className="text-xs text-base-content/50">Cron expression</label>
                  <div className="flex gap-2 items-center flex-wrap">
                    <input
                      className="input input-bordered input-sm font-mono w-44"
                      value={cronExpr}
                      onChange={e => setCronExpr(e.target.value)}
                      placeholder="0 * * * *"
                    />
                    <span className="text-xs opacity-40">min hour day month weekday</span>
                  </div>
                  <div className="flex gap-1 flex-wrap mt-1">
                    {[
                      { label: 'Every hour',    val: '0 * * * *' },
                      { label: 'Every 6h',      val: '0 */6 * * *' },
                      { label: 'Daily 3am',     val: '0 3 * * *' },
                      { label: 'Every Monday',  val: '0 9 * * 1' },
                    ].map(p => (
                      <button key={p.val} onClick={() => setCronExpr(p.val)}
                        className={`btn btn-xs btn-ghost font-mono text-xs ${cronExpr === p.val ? 'btn-active' : ''}`}>
                        {p.label}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Target group */}
              <div className="flex gap-2 items-center flex-wrap">
                <span className="text-xs font-semibold text-base-content/50 uppercase">Target</span>
                <select
                  className="select select-bordered select-sm"
                  value={agentGroup[0]}
                  onChange={e => setAgentGroup([e.target.value])}
                >
                  <option value="all">All agents</option>
                  {groups.map((g: any) => (
                    <option key={g.id} value={g.id}>{g.name}</option>
                  ))}
                </select>

                {/* Status toggle */}
                <span className="text-xs font-semibold text-base-content/50 uppercase ml-3">Status</span>
                <label className="flex items-center gap-1 cursor-pointer">
                  <input type="checkbox" className="toggle toggle-xs toggle-success"
                    checked={tlStatus === 'active'}
                    onChange={e => setTlStatus(e.target.checked ? 'active' : 'draft')} />
                  <span className={`text-xs ${tlStatus === 'active' ? 'text-green-400' : 'opacity-50'}`}>
                    {tlStatus === 'active' ? 'Active' : 'Draft'}
                  </span>
                </label>
              </div>
            </div>

            <div className="space-y-2">
              {steps.map((step, i) => (
                <StepBlock
                  key={i} step={step} index={i} total={steps.length}
                  onChange={(s) => updateStep(i, s)}
                  onRemove={() => removeStep(i)}
                  onMove={(dir) => moveStep(i, dir)}
                />
              ))}
            </div>

            <button className="btn btn-sm btn-dashed w-full gap-1" onClick={() => addStep()}>
              <Plus size={14} /> Add Step
            </button>

            {execResult && (
              <div className="alert alert-info text-xs font-mono">
                <span>{execResult}</span>
                <button className="btn btn-xs btn-ghost ml-auto" onClick={() => setExecResult(null)}>✕</button>
              </div>
            )}
          </>
        ) : (
          <div className="flex flex-col items-center justify-center h-64 text-base-content/30">
            <p>Select a timeline or create a new one</p>
          </div>
        )}
      </div>

      {/* Right — Module palette */}
      <aside className="w-48 flex flex-col gap-2 shrink-0 overflow-y-auto scrollbar-thin">
        <span className="text-sm font-semibold">Modules</span>
        <input className="input input-xs input-bordered" placeholder="Search…" value={moduleSearch} onChange={(e) => setModuleSearch(e.target.value)} />
        {filteredModules.map((m: any) => (
          <div
            key={m.id}
            draggable
            className="card bg-base-200 p-2 cursor-grab text-xs hover:bg-base-300 transition-colors"
            onClick={() => addStep(m.name)}
          >
            <p className="font-medium">{m.name}</p>
            <p className="text-base-content/40 truncate">{m.version}</p>
          </div>
        ))}
      </aside>
    </div>
  )
}
