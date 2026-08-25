import { useState, useRef, useEffect } from 'react'
import { useAgentStore } from '../stores/agentStore'
import { useCreateTask } from '../hooks/useTasks'
import { Terminal as TermIcon, Send, Trash2 } from 'lucide-react'

interface Line { id: string; kind: 'input' | 'output' | 'error' | 'info'; text: string; agent?: string }

export default function Terminal() {
  const agents = useAgentStore((s) => s.agentsArray)
  const { mutateAsync: createTask } = useCreateTask()
  const [selectedAgents, setSelectedAgents] = useState<string[]>([])
  const [cmd, setCmd] = useState('')
  const [lines, setLines] = useState<Line[]>([
    { id: '0', kind: 'info', text: 'Lucy C2 Terminal — broadcast shell, type a command and press Enter or ↵' },
  ])
  const [busy, setBusy] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [lines])

  const push = (kind: Line['kind'], text: string, agent?: string) =>
    setLines((prev) => [...prev, { id: Math.random().toString(36).slice(2), kind, text, agent }])

  const handleRun = async () => {
    if (!cmd.trim() || busy) return
    const targets = selectedAgents.length ? selectedAgents : agents.filter((a) => a.status === 'online').map((a) => a.id)
    if (!targets.length) { push('error', 'No online agents selected.'); return }

    push('input', `$ ${cmd}  [→ ${targets.length} agent(s)]`)
    setBusy(true)

    await Promise.allSettled(
      targets.map(async (agent_id) => {
        try {
          const task = await createTask({ agent_id, module: 'shell', action: 'exec', params: { cmd }, priority: 'high' } as any)
          push('info', `[${agents.find((a) => a.id === agent_id)?.hostname ?? agent_id}] task ${String(task.id).slice(0, 8)} queued`, agent_id)
        } catch (e: any) {
          push('error', `[${agent_id}] failed: ${e.message}`, agent_id)
        }
      })
    )
    setCmd('')
    setBusy(false)
  }

  const toggleAgent = (id: string) =>
    setSelectedAgents((prev) => prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id])

  return (
    <div className="page-container flex gap-4 h-[calc(100vh-3.5rem)] overflow-hidden">
      {/* Agent selector */}
      <aside className="w-52 shrink-0 overflow-y-auto scrollbar-thin space-y-1">
        <p className="text-xs font-semibold text-base-content/50 mb-2">Target Agents</p>
        <button
          className={`btn btn-xs w-full mb-2 ${selectedAgents.length === 0 ? 'btn-success' : 'btn-outline'}`}
          onClick={() => setSelectedAgents([])}
        >All Online</button>
        {agents.map((a) => (
          <div
            key={a.id}
            onClick={() => toggleAgent(a.id)}
            className={`card p-2 cursor-pointer text-xs transition-colors ${selectedAgents.includes(a.id) ? 'bg-success/20 border border-success/40' : 'bg-base-200 hover:bg-base-300'}`}
          >
            <p className="font-mono truncate">{a.hostname}</p>
            <span className={`badge badge-xs badge-${a.status === 'online' ? 'success' : 'error'}`}>{a.status}</span>
          </div>
        ))}
      </aside>

      {/* Terminal pane */}
      <div className="flex-1 flex flex-col bg-base-300 rounded-xl overflow-hidden border border-base-content/10">
        <div className="flex items-center gap-2 px-4 py-2 bg-base-300 border-b border-base-content/10">
          <TermIcon size={14} className="text-success" />
          <span className="text-xs font-mono text-success">lucy@c2:~#</span>
          <div className="flex-1" />
          <button className="btn btn-xs btn-ghost" onClick={() => setLines([])}>
            <Trash2 size={12} /> Clear
          </button>
        </div>

        <div className="flex-1 overflow-y-auto scrollbar-thin px-4 py-3 font-mono text-sm space-y-1">
          {lines.map((l) => (
            <div key={l.id} className={
              l.kind === 'input' ? 'text-success' :
              l.kind === 'error' ? 'text-error' :
              l.kind === 'info' ? 'text-base-content/50' : 'text-base-content'
            }>
              <span>{l.text}</span>
            </div>
          ))}
          <div ref={bottomRef} />
        </div>

        <div className="flex gap-2 p-3 border-t border-base-content/10">
          <span className="font-mono text-success self-center">$</span>
          <input
            className="flex-1 bg-transparent font-mono text-sm outline-none"
            value={cmd}
            onChange={(e) => setCmd(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') handleRun() }}
            placeholder="command…"
            autoFocus
            disabled={busy}
          />
          <button className="btn btn-xs btn-success gap-1" onClick={handleRun} disabled={busy || !cmd.trim()}>
            {busy ? <span className="loading loading-spinner loading-xs" /> : <Send size={12} />} Send
          </button>
        </div>
      </div>
    </div>
  )
}
