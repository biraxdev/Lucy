import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  addEdge,
  useNodesState,
  useEdgesState,
  type Connection,
  type Edge,
  type Node,
  type ReactFlowInstance,
  Panel,
} from 'reactflow'
import 'reactflow/dist/style.css'
import {
  Play,
  Save,
  Download,
  Upload,
  Plus,
  Activity,
  Edit3,
  ArrowRight,
  Zap,
  MousePointer,
  Clock,
  BookOpen,
  AlertCircle,
} from 'lucide-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { getModules } from '../api/modules'
import { listGroups } from '../api/groups'
import { createTimeline, executeTimeline, getTimelineTasks, getPocs, importPoc, updateTimeline } from '../api/tasks'
import { useWebSocket } from '../hooks/useWebSocket'
import type { Module } from '../types/module'
import type { AgentGroup } from '../api/groups'
import type { Timeline, TimelineStep, Task } from '../types/task'

import ModulePalette from '../components/script-builder/ModulePalette'
import ParamEditor from '../components/script-builder/ParamEditor'
import ModuleNode, { type ModuleNodeData } from '../components/script-builder/ModuleNode'

const nodeTypes = { moduleNode: ModuleNode }

function uid() {
  return Math.random().toString(36).slice(2, 9)
}

function buildDefaultParams(module: Module): Record<string, unknown> {
  const schema = module.params_schema || {}
  const defaults: Record<string, unknown> = {}
  for (const [key, def] of Object.entries(schema.properties || {})) {
    const d = def as any
    if ('default' in d) defaults[key] = d.default
    else if (d.type === 'boolean') defaults[key] = false
    else if (d.type === 'number' || d.type === 'integer') defaults[key] = 0
    else if (d.type === 'array') defaults[key] = []
    else defaults[key] = ''
  }
  return defaults
}

function createModuleNode(module: Module, position: { x: number; y: number }): Node<ModuleNodeData> {
  const action = module.actions?.[0] || 'run'
  return {
    id: uid(),
    type: 'moduleNode',
    position,
    data: {
      module: module.name,
      action,
      params: { ...buildDefaultParams(module) },
      delay: 0,
      timeout: 60,
      priority: 'normal',
      description: module.description || '',
      status: 'idle',
    },
  }
}

function topologicalSort(nodes: Node<ModuleNodeData>[], edges: Edge[]): Node<ModuleNodeData>[] {
  const adj = new Map<string, string[]>()
  const inDegree = new Map<string, number>()
  for (const n of nodes) {
    adj.set(n.id, [])
    inDegree.set(n.id, 0)
  }
  for (const e of edges) {
    adj.get(e.source)?.push(e.target)
    inDegree.set(e.target, (inDegree.get(e.target) || 0) + 1)
  }
  const queue = nodes.filter((n) => (inDegree.get(n.id) || 0) === 0).map((n) => n.id)
  const result: Node<ModuleNodeData>[] = []
  while (queue.length > 0) {
    const id = queue.shift()!
    const node = nodes.find((n) => n.id === id)
    if (node) result.push(node)
    for (const next of adj.get(id) || []) {
      const deg = (inDegree.get(next) || 0) - 1
      inDegree.set(next, deg)
      if (deg === 0) queue.push(next)
    }
  }
  if (result.length < nodes.length) {
    // Fallback to x-position order if cycle or disconnected
    return [...nodes].sort((a, b) => a.position.x - b.position.x)
  }
  return result
}

function nodesToTimelineSteps(nodes: Node<ModuleNodeData>[], edges: Edge[]): TimelineStep[] {
  const ordered = topologicalSort(nodes, edges)
  return ordered.map((n, idx) => ({
    order: idx + 1,
    module: n.data.module,
    action: n.data.action,
    params: { ...n.data.params, _node_id: n.id },
    delay: n.data.delay,
    timeout: n.data.timeout,
    priority: n.data.priority as any,
  }))
}

function stepsToNodes(steps: TimelineStep[]): Node<ModuleNodeData>[] {
  return steps.map((s, idx) => ({
    id: (s.params as any)?._node_id || uid(),
    type: 'moduleNode',
    position: { x: idx * 220 + 40, y: 80 },
    data: {
      module: s.module,
      action: s.action,
      params: { ...(s.params || {}) },
      delay: s.delay,
      timeout: s.timeout,
      priority: s.priority,
      description: (s as any).action_description || '',
      status: 'idle',
    },
  }))
}

export default function ScriptBuilder() {
  const qc = useQueryClient()
  const reactFlowWrapper = useRef<HTMLDivElement>(null)
  const [rfInstance, setRfInstance] = useState<ReactFlowInstance | null>(null)
  const [nodes, setNodes, onNodesChange] = useNodesState<ModuleNodeData>([])
  const [edges, setEdges, onEdgesChange] = useEdgesState([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [name, setName] = useState('New Script')
  const [description, setDescription] = useState('')
  const [agentGroup, setAgentGroup] = useState<string[]>(['all'])
  const [timelineId, setTimelineId] = useState<string | null>(null)
  const [liveMode, setLiveMode] = useState(false)
  const [executing, setExecuting] = useState(false)
  const [error, setError] = useState('')
  const [pocSearch, setPocSearch] = useState('')
  const [showPocs, setShowPocs] = useState(false)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const { data: modules = [] } = useQuery({ queryKey: ['modules'], queryFn: getModules })
  const { data: groups = [] } = useQuery({ queryKey: ['groups'], queryFn: listGroups })
  const { data: pocs = [] } = useQuery({ queryKey: ['pocs'], queryFn: getPocs })

  const createMut = useMutation({
    mutationFn: createTimeline,
    onSuccess: (tl) => {
      qc.invalidateQueries({ queryKey: ['timelines'] })
      setTimelineId(tl.id)
    },
  })

  const updateMut = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<Timeline> }) => updateTimeline(id, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['timelines'] }),
  })

  const importPocMut = useMutation({
    mutationFn: importPoc,
    onSuccess: (tl) => {
      setTimelineId(tl.id)
      setName(tl.name)
      setDescription(tl.description || '')
      setAgentGroup(tl.agent_group || ['all'])
      setNodes(stepsToNodes(tl.steps || []))
      setEdges([])
      setShowPocs(false)
      qc.invalidateQueries({ queryKey: ['timelines'] })
    },
  })

  const { on: onWS } = useWebSocket()

  const selectedNode = useMemo(() => nodes.find((n) => n.id === selectedId) || null, [nodes, selectedId])

  const onConnect = useCallback(
    (connection: Connection) => setEdges((eds) => addEdge({ ...connection, animated: true, style: { stroke: '#22c55e' } }, eds)),
    [setEdges]
  )

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault()
      if (!reactFlowWrapper.current || !rfInstance) return
      const raw = event.dataTransfer.getData('application/reactflow')
      if (!raw) return
      const module: Module = JSON.parse(raw)
      const bounds = reactFlowWrapper.current.getBoundingClientRect()
      const position = rfInstance.screenToFlowPosition({ x: event.clientX - bounds.left, y: event.clientY - bounds.top })
      const node = createModuleNode(module, position)
      setNodes((nds) => [...nds, node])
    },
    [rfInstance, setNodes]
  )

  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault()
    event.dataTransfer.dropEffect = 'move'
  }, [])

  const updateNode = useCallback(
    (id: string, patch: Partial<ModuleNodeData>) => {
      setNodes((nds) =>
        nds.map((n) => (n.id === id ? { ...n, data: { ...n.data, ...patch } } : n))
      )
    },
    [setNodes]
  )

  const removeNode = useCallback(
    (id: string) => {
      setNodes((nds) => nds.filter((n) => n.id !== id))
      setEdges((eds) => eds.filter((e) => e.source !== id && e.target !== id))
      setSelectedId(null)
    },
    [setNodes, setEdges]
  )

  const moveNode = useCallback(
    (id: string, dir: -1 | 1) => {
      const idx = nodes.findIndex((n) => n.id === id)
      const j = idx + dir
      if (j < 0 || j >= nodes.length) return
      const arr = [...nodes]
      ;[arr[idx], arr[j]] = [arr[j], arr[idx]]
      setNodes(arr)
    },
    [nodes, setNodes]
  )

  const save = async () => {
    const steps = nodesToTimelineSteps(nodes, edges)
    const payload = { name, description, agent_group: agentGroup, steps, trigger: 'manual' as const, loop: false as const, status: 'draft' as const }
    if (timelineId) {
      await updateMut.mutateAsync({ id: timelineId, data: payload })
    } else {
      const tl = await createMut.mutateAsync(payload)
      setTimelineId(tl.id)
    }
  }

  const execute = async () => {
    setError('')
    // Save first and wait for the timeline ID to be available
    let id = timelineId
    if (!id) {
      try {
        await save()
        // save() sets timelineId via setTimelineId, but state updates are async
        // so use the mutation result directly
        id = createMut.data?.id || timelineId
      } catch (e: any) {
        setError(e?.response?.data?.detail || e?.message || 'Failed to save timeline before execute')
        return
      }
    }
    if (!id) {
      setError('No timeline ID available — save failed silently')
      return
    }
    setExecuting(true)
    setLiveMode(true)
    try {
      await executeTimeline(id)
    } catch (e: any) {
      setError(e?.response?.data?.detail || e?.message || 'Failed to execute timeline')
      setExecuting(false)
      return
    }
    // Start polling
    if (pollRef.current) clearInterval(pollRef.current)
    pollRef.current = setInterval(async () => {
      try {
        const tasks = await getTimelineTasks(id!)
        updateLiveNodes(tasks)
      } catch {}
    }, 2000)
  }

  const updateLiveNodes = (tasks: Task[]) => {
    setNodes((nds) =>
      nds.map((n) => {
        const nodeId = n.id
        const task = tasks.find((t) => (t.params as any)?._node_id === nodeId)
        if (!task) return n
        return {
          ...n,
          data: { ...n.data, status: task.status, taskId: task.id, result: task.result, error: task.error },
        }
      })
    )
  }

  useEffect(() => {
    const unsub = onWS('result', (msg) => {
      const payload = msg.payload as any
      const taskId = payload?.id ?? payload?.task_id
      if (!taskId) return
      // Refetch tasks on result to update node status
      if (timelineId) {
        getTimelineTasks(timelineId).then(updateLiveNodes).catch(() => {})
      }
    })
    return unsub
  }, [onWS, timelineId])

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [])

  const exportJSON = () => {
    const steps = nodesToTimelineSteps(nodes, edges)
    const blob = new Blob([JSON.stringify({ name, description, agent_group: agentGroup, steps }, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${name.replace(/\s+/g, '_').toLowerCase()}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  const importJSON = async (file: File) => {
    const text = await file.text()
    const data = JSON.parse(text)
    setName(data.name || 'Imported Script')
    setDescription(data.description || '')
    setAgentGroup(data.agent_group || ['all'])
    setNodes(stepsToNodes(data.steps || []))
    setEdges([])
    setTimelineId(null)
  }

  const filteredPocs = pocs.filter((p: any) =>
    p.name.toLowerCase().includes(pocSearch.toLowerCase()) ||
    (p.description || '').toLowerCase().includes(pocSearch.toLowerCase()) ||
    (p.category || '').toLowerCase().includes(pocSearch.toLowerCase())
  )

  return (
    <div className="page-container flex flex-col h-[calc(100vh-3.5rem)] overflow-hidden p-0">
      {/* Header toolbar */}
      <div className="flex items-center gap-3 px-4 py-2 border-b border-base-300 bg-base-200">
        <h1 className="text-lg font-bold flex items-center gap-2">
          {liveMode ? <Activity size={20} className="text-success animate-pulse" /> : <Edit3 size={20} />}
          {liveMode ? 'Live Execution' : 'Script Builder'}
        </h1>
        <input
          className="input input-sm input-bordered w-56"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Script name"
        />
        <input
          className="input input-sm input-bordered flex-1 min-w-0"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Description…"
        />
        <select
          className="select select-sm select-bordered"
          value={agentGroup[0] || 'all'}
          onChange={(e) => setAgentGroup([e.target.value])}
        >
          <option value="all">All agents</option>
          {groups.map((g: AgentGroup) => (
            <option key={g.id} value={g.id}>{g.name}</option>
          ))}
        </select>
        <div className="flex gap-1">
          <button className="btn btn-sm btn-outline gap-1" onClick={() => setShowPocs(true)}><BookOpen size={14} /> PoCs</button>
          <button className="btn btn-sm btn-outline gap-1" onClick={exportJSON}><Download size={14} /></button>
          <label className="btn btn-sm btn-outline gap-1 cursor-pointer">
            <Upload size={14} />
            <input type="file" accept=".json" className="hidden" onChange={(e) => e.target.files?.[0] && importJSON(e.target.files[0])} />
          </label>
          <button className="btn btn-sm btn-outline gap-1" onClick={save} disabled={createMut.isPending || updateMut.isPending}>
            <Save size={14} /> Save
          </button>
          <button className="btn btn-sm btn-success gap-1" onClick={execute} disabled={executing || nodes.length === 0}>
            <Play size={14} /> {executing ? 'Running…' : 'Execute'}
          </button>
        </div>
      </div>

      {error && (
        <div className="alert alert-error text-xs py-2 px-3 flex items-center gap-2">
          <AlertCircle size={14} className="shrink-0" />
          <span>{error}</span>
          <button className="btn btn-xs btn-ghost ml-auto" onClick={() => setError('')}>×</button>
        </div>
      )}

      {/* Main workspace */}
      <div className="flex flex-1 overflow-hidden">
        <ModulePalette modules={modules} />

        <div className="flex-1 flex flex-col min-w-0">
          <div ref={reactFlowWrapper} className="flex-1" onDrop={onDrop} onDragOver={onDragOver}>
            <ReactFlow
              nodes={nodes}
              edges={edges}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              onConnect={onConnect}
              onInit={setRfInstance}
              nodeTypes={nodeTypes}
              onNodeClick={(_, n) => setSelectedId(n.id)}
              onPaneClick={() => setSelectedId(null)}
              fitView
            >
              <Background gap={16} size={1} />
              <Controls />
              <MiniMap nodeStrokeWidth={3} zoomable pannable />
              <Panel position="top-left" className="bg-base-200/80 backdrop-blur rounded-lg p-2 text-xs space-y-1">
                <div className="flex items-center gap-1"><MousePointer size={12} /> Drag module here</div>
                <div className="flex items-center gap-1"><ArrowRight size={12} /> Connect nodes to set order</div>
                <div className="flex items-center gap-1"><Zap size={12} /> Click Execute to run live</div>
              </Panel>
              {liveMode && (
                <Panel position="bottom-center" className="bg-base-200/90 backdrop-blur rounded-full px-4 py-1 text-xs font-mono">
                  <span className="text-success flex items-center gap-2">
                    <Activity size={12} className="animate-pulse" /> Live monitoring active
                  </span>
                </Panel>
              )}
            </ReactFlow>
          </div>

          {/* Live detail panel */}
          {liveMode && selectedNode?.data.taskId && (
            <div className="h-48 bg-base-200 border-t border-base-300 p-3 overflow-y-auto">
              <div className="flex items-center gap-2 mb-2">
                <span className="font-mono text-sm">{selectedNode.data.module}:{selectedNode.data.action}</span>
                <span className={`badge badge-xs badge-${selectedNode.data.status === 'completed' ? 'success' : selectedNode.data.status === 'failed' ? 'error' : 'info'}`}>{selectedNode.data.status}</span>
                <span className="text-xs text-base-content/40">Task {selectedNode.data.taskId?.slice(0, 8)}</span>
              </div>
              <div className="grid grid-cols-2 gap-4 text-xs">
                <div>
                  <p className="text-base-content/40 uppercase text-[10px] font-bold">Request params</p>
                  <pre className="bg-base-300 rounded p-2 overflow-x-auto font-mono text-[10px]">{JSON.stringify(selectedNode.data.params, null, 2)}</pre>
                </div>
                <div>
                  <p className="text-base-content/40 uppercase text-[10px] font-bold">Response</p>
                  {selectedNode.data.error ? (
                    <pre className="bg-error/10 text-error rounded p-2 overflow-x-auto font-mono text-[10px]">{selectedNode.data.error}</pre>
                  ) : (
                    <pre className="bg-base-300 rounded p-2 overflow-x-auto font-mono text-[10px]">{JSON.stringify(selectedNode.data.result, null, 2)}</pre>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>

        <ParamEditor
          nodeData={selectedNode?.data || null}
          modules={modules}
          onChange={(data) => selectedId && updateNode(selectedId, data)}
          onRemove={() => selectedId && removeNode(selectedId)}
          onMove={(dir) => selectedId && moveNode(selectedId, dir)}
          canMoveUp={!!selectedId && nodes.findIndex((n) => n.id === selectedId) > 0}
          canMoveDown={!!selectedId && nodes.findIndex((n) => n.id === selectedId) < nodes.length - 1}
        />
      </div>

      {/* PoC import modal */}
      {showPocs && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="bg-base-100 border border-base-300 rounded-2xl shadow-2xl w-full max-w-2xl p-6 max-h-[80vh] flex flex-col">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-bold flex items-center gap-2"><BookOpen size={20} className="text-success" /> PoC Library</h2>
              <button className="btn btn-sm btn-ghost" onClick={() => setShowPocs(false)}>✕</button>
            </div>
            <input
              className="input input-sm input-bordered w-full mb-4"
              placeholder="Search PoC…"
              value={pocSearch}
              onChange={(e) => setPocSearch(e.target.value)}
            />
            <div className="flex-1 overflow-y-auto space-y-2">
              {filteredPocs.map((p: any) => (
                <div key={p.puid} className="border border-base-300 rounded-xl p-3 hover:border-success/50 transition-colors">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="text-xl">{p.icon}</span>
                      <span className="font-bold text-sm">{p.name}</span>
                      <span className="badge badge-xs badge-ghost">{p.category}</span>
                    </div>
                    <button
                      className="btn btn-xs btn-success gap-1"
                      onClick={() => importPocMut.mutate(p.puid)}
                      disabled={importPocMut.isPending}
                    >
                      <Plus size={12} /> Import
                    </button>
                  </div>
                  <p className="text-xs text-base-content/50 mt-1 line-clamp-2">{p.description}</p>
                  <p className="text-[10px] text-base-content/30 mt-1">{p.steps?.length || 0} steps · {p.trigger}</p>
                </div>
              ))}
              {filteredPocs.length === 0 && <p className="text-sm text-base-content/40 text-center py-4">No PoC found.</p>}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
