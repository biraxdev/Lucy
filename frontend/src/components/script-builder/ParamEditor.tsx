import { useEffect, useState } from 'react'
import { Trash2, ChevronDown, ChevronUp } from 'lucide-react'
import type { Module } from '../../types/module'
import type { ModuleNodeData } from './ModuleNode'

interface ParamEditorProps {
  nodeData: ModuleNodeData | null
  modules: Module[]
  onChange: (data: ModuleNodeData) => void
  onRemove: () => void
  onMove: (dir: -1 | 1) => void
  canMoveUp: boolean
  canMoveDown: boolean
}

function buildDefaultParams(schema: Record<string, any> = {}): Record<string, any> {
  const defaults: Record<string, any> = {}
  for (const [key, def] of Object.entries(schema.properties || {})) {
    if ('default' in (def as any)) defaults[key] = (def as any).default
    else if ((def as any).type === 'boolean') defaults[key] = false
    else if ((def as any).type === 'number') defaults[key] = 0
    else if ((def as any).type === 'integer') defaults[key] = 0
    else if ((def as any).type === 'array') defaults[key] = []
    else defaults[key] = ''
  }
  return defaults
}

export default function ParamEditor({ nodeData, modules, onChange, onRemove, onMove, canMoveUp, canMoveDown }: ParamEditorProps) {
  const [rawParams, setRawParams] = useState('')

  const module = nodeData ? modules.find((m) => m.name === nodeData.module) : null
  const actions = module?.actions || ['run']
  const schema = module?.params_schema || {}

  useEffect(() => {
    if (nodeData) setRawParams(JSON.stringify(nodeData.params, null, 2))
  }, [nodeData])

  if (!nodeData) {
    return (
      <div className="w-72 bg-base-200 border-l border-base-300 p-4 h-full">
        <p className="text-sm text-base-content/40">Select a module node to configure its action and parameters.</p>
      </div>
    )
  }

  const update = (patch: Partial<ModuleNodeData>) => {
    onChange({ ...nodeData, ...patch })
  }

  const applyRawParams = () => {
    try {
      const parsed = JSON.parse(rawParams)
      update({ params: parsed })
    } catch {}
  }

  const actionChanged = (action: string) => {
    // Reset params to schema defaults when action changes
    const newParams = buildDefaultParams(schema)
    setRawParams(JSON.stringify(newParams, null, 2))
    update({ action, params: newParams })
  }

  const setParam = (key: string, value: any) => {
    const next = { ...nodeData.params, [key]: value }
    update({ params: next })
    setRawParams(JSON.stringify(next, null, 2))
  }

  return (
    <div className="w-72 bg-base-200 border-l border-base-300 p-4 h-full overflow-y-auto">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-bold">Configure</h3>
        <div className="flex gap-1">
          <button className="btn btn-xs btn-ghost" onClick={() => onMove(-1)} disabled={!canMoveUp}><ChevronUp size={12} /></button>
          <button className="btn btn-xs btn-ghost" onClick={() => onMove(1)} disabled={!canMoveDown}><ChevronDown size={12} /></button>
          <button className="btn btn-xs btn-ghost text-error" onClick={onRemove}><Trash2 size={12} /></button>
        </div>
      </div>

      <div className="space-y-3">
        <label className="text-xs text-base-content/60 block">Module
          <input className="input input-xs input-bordered w-full mt-1 font-mono" value={nodeData.module} disabled />
        </label>

        <label className="text-xs text-base-content/60 block">Action
          <select
            className="select select-xs select-bordered w-full mt-1"
            value={nodeData.action}
            onChange={(e) => actionChanged(e.target.value)}
          >
            {actions.map((a) => <option key={a}>{a}</option>)}
          </select>
        </label>

        {module?.description && (
          <p className="text-xs text-base-content/50 leading-relaxed">{module.description}</p>
        )}

        <div className="grid grid-cols-2 gap-2">
          <label className="text-xs text-base-content/60 block">Delay (s)
            <input
              type="number"
              min={0}
              className="input input-xs input-bordered w-full mt-1"
              value={nodeData.delay}
              onChange={(e) => update({ delay: Number(e.target.value) })}
            />
          </label>
          <label className="text-xs text-base-content/60 block">Timeout (s)
            <input
              type="number"
              min={1}
              className="input input-xs input-bordered w-full mt-1"
              value={nodeData.timeout}
              onChange={(e) => update({ timeout: Number(e.target.value) })}
            />
          </label>
        </div>

        <label className="text-xs text-base-content/60 block">Priority
          <select
            className="select select-xs select-bordered w-full mt-1"
            value={nodeData.priority}
            onChange={(e) => update({ priority: e.target.value })}
          >
            {['critical', 'high', 'normal', 'low'].map((p) => <option key={p}>{p}</option>)}
          </select>
        </label>

        <label className="text-xs text-base-content/60 block">Step description
          <input
            className="input input-xs input-bordered w-full mt-1"
            value={nodeData.description || ''}
            onChange={(e) => update({ description: e.target.value })}
            placeholder="What this step does"
          />
        </label>

        <div className="divider text-[10px] text-base-content/30">Parameters (JSON)</div>

        <textarea
          className="textarea textarea-bordered w-full font-mono text-xs"
          rows={6}
          value={rawParams}
          onChange={(e) => setRawParams(e.target.value)}
          onBlur={applyRawParams}
        />

        {Object.keys(schema.properties || {}).length > 0 && (
          <div className="space-y-2">
            <p className="text-[10px] font-semibold uppercase text-base-content/40">Quick fields</p>
            {Object.entries(schema.properties || {}).map(([key, def]: [string, any]) => {
              const val = nodeData.params[key]
              if (def.type === 'boolean') {
                return (
                  <label key={key} className="flex items-center gap-2 text-xs cursor-pointer">
                    <input
                      type="checkbox"
                      className="checkbox checkbox-xs"
                      checked={!!val}
                      onChange={(e) => setParam(key, e.target.checked)}
                    />
                    {key}
                  </label>
                )
              }
              if (def.type === 'array') {
                return (
                  <label key={key} className="text-xs text-base-content/60 block">
                    {key}
                    <input
                      className="input input-xs input-bordered w-full mt-1 font-mono"
                      value={Array.isArray(val) ? JSON.stringify(val) : typeof val === 'string' || typeof val === 'number' ? String(val || '') : ''}
                      onChange={(e) => { try { setParam(key, JSON.parse(e.target.value)) } catch {} }}
                    />
                  </label>
                )
              }
              return (
                <label key={key} className="text-xs text-base-content/60 block">
                  {key}
                  <input
                    className="input input-xs input-bordered w-full mt-1 font-mono"
                    value={typeof val === 'string' || typeof val === 'number' ? String(val) : ''}
                    onChange={(e) => setParam(key, e.target.value)}
                  />
                </label>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
