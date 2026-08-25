import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Bell, BellOff, CheckCheck, Plus, Trash2, Send, Webhook,
  AlertTriangle, Info, ShieldAlert, Loader2, RefreshCw, X,
  Zap, ArrowRight,
} from 'lucide-react'
import {
  listAlerts, markRead, listWebhooks, addWebhook, removeWebhook, testWebhook,
} from '../api/alerts'
import type { Alert } from '../api/alerts'
import { useWebSocket } from '../hooks/useWebSocket'
import api from '../api/client'
import { useToast } from '../contexts/ToastContext'

// ---------------------------------------------------------------------------
// Severity helpers
// ---------------------------------------------------------------------------

const SEV_STYLES: Record<string, string> = {
  critical: 'bg-red-500/10 border-red-500/30 text-red-400',
  warning:  'bg-yellow-500/10 border-yellow-500/30 text-yellow-400',
  info:     'bg-blue-500/10 border-blue-500/30 text-blue-400',
}
const SEV_ICON: Record<string, JSX.Element> = {
  critical: <ShieldAlert size={14} className="text-red-400 shrink-0" />,
  warning:  <AlertTriangle size={14} className="text-yellow-400 shrink-0" />,
  info:     <Info size={14} className="text-blue-400 shrink-0" />,
}
const EVENT_LABELS: Record<string, string> = {
  agent_connect:    '🟢 Agent Connected',
  agent_disconnect: '⚫ Agent Disconnected',
  credential_found: '🔑 Credentials Found',
  task_failed:      '❌ Task Failed',
  timeline_done:    '✅ Timeline Done',
  custom:           '📌 Custom',
  test:             '🧪 Test',
}

function AlertRow({ alert, onRead }: { alert: Alert; onRead: (id: string) => void }) {
  const toast = useToast()

  const actOnAlert = async (e: React.MouseEvent) => {
    e.stopPropagation()
    if (!alert.agent_id) {
      toast.addToast({ type: 'warning', title: 'No agent linked', message: 'This alert has no associated agent to act on.' })
      return
    }
    try {
      const res = await api.post(`/alerts/${alert.id}/to-task`, {
        module: 'shell',
        action: 'run',
        params: { cmd: 'whoami && hostname && ipconfig' },
        priority: 'high',
      })
      toast.addToast({ type: 'success', title: 'Task dispatched', message: res.data?.message || 'Alert converted to task' })
      onRead(alert.id)
    } catch (err: any) {
      toast.addToast({ type: 'error', title: 'Action failed', message: err?.message || 'Could not dispatch task from alert' })
    }
  }

  return (
    <div
      className={`flex items-start gap-3 px-4 py-3 rounded-lg border transition-all cursor-pointer
        ${alert.read ? 'opacity-50' : ''}
        ${SEV_STYLES[alert.severity] || SEV_STYLES.info}`}
      onClick={() => !alert.read && onRead(alert.id)}
    >
      {SEV_ICON[alert.severity] || SEV_ICON.info}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs font-bold opacity-70">
            {EVENT_LABELS[alert.event] || alert.event}
          </span>
          {!alert.read && (
            <span className="w-2 h-2 rounded-full bg-current shrink-0" />
          )}
        </div>
        <p className="text-sm font-medium mt-0.5">{alert.title}</p>
        <p className="text-xs opacity-60 mt-0.5 truncate">{alert.message}</p>
      </div>
      {alert.agent_id && (
        <button
          onClick={actOnAlert}
          className="btn btn-xs btn-success gap-1 shrink-0 mt-0.5"
          title="Dispatch a task to investigate this alert"
        >
          <Zap size={10} /> Act <ArrowRight size={8} />
        </button>
      )}
      <span className="text-xs opacity-40 shrink-0 mt-0.5">
        {new Date(alert.timestamp).toLocaleTimeString()}
      </span>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Webhook form modal
// ---------------------------------------------------------------------------

const EMPTY_HOOK = {
  name: '', url: '', kind: 'generic' as const,
  enabled: true, min_severity: 'warning' as const,
  events: [] as string[], secret: '', username: '',
}

const KIND_OPTIONS = ['generic', 'slack', 'discord'] as const
const SEV_OPTIONS  = ['info', 'warning', 'critical'] as const
const EVENT_OPTIONS = ['agent_connect', 'agent_disconnect', 'credential_found', 'task_failed', 'timeline_done']

function WebhookModal({ onClose, onSave }: { onClose: () => void; onSave: (w: typeof EMPTY_HOOK) => void }) {
  const [form, setForm] = useState({ ...EMPTY_HOOK })

  const toggleEvent = (ev: string) => {
    setForm(f => ({
      ...f,
      events: f.events.includes(ev) ? f.events.filter(e => e !== ev) : [...f.events, ev],
    }))
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="bg-base-200 border border-base-300 rounded-xl w-full max-w-lg p-6 shadow-2xl space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="font-bold text-lg flex items-center gap-2"><Webhook size={18}/> Add Webhook</h3>
          <button onClick={onClose} className="btn btn-ghost btn-sm btn-circle"><X size={16}/></button>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div className="col-span-2">
            <label className="text-xs text-base-content/50 mb-1 block">Name</label>
            <input className="input input-bordered input-sm w-full" value={form.name}
              onChange={e => setForm(f => ({ ...f, name: e.target.value }))} placeholder="My Slack webhook" />
          </div>
          <div className="col-span-2">
            <label className="text-xs text-base-content/50 mb-1 block">URL</label>
            <input className="input input-bordered input-sm w-full" value={form.url}
              onChange={e => setForm(f => ({ ...f, url: e.target.value }))} placeholder="https://hooks.slack.com/..." />
          </div>
          <div>
            <label className="text-xs text-base-content/50 mb-1 block">Kind</label>
            <select className="select select-bordered select-sm w-full" value={form.kind}
              onChange={e => setForm(f => ({ ...f, kind: e.target.value as any }))}>
              {KIND_OPTIONS.map(k => <option key={k} value={k}>{k}</option>)}
            </select>
          </div>
          <div>
            <label className="text-xs text-base-content/50 mb-1 block">Min Severity</label>
            <select className="select select-bordered select-sm w-full" value={form.min_severity}
              onChange={e => setForm(f => ({ ...f, min_severity: e.target.value as any }))}>
              {SEV_OPTIONS.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
          <div className="col-span-2">
            <label className="text-xs text-base-content/50 mb-1 block">Events (empty = all)</label>
            <div className="flex flex-wrap gap-2 mt-1">
              {EVENT_OPTIONS.map(ev => (
                <button key={ev} onClick={() => toggleEvent(ev)}
                  className={`btn btn-xs ${form.events.includes(ev) ? 'btn-success' : 'btn-ghost'}`}>
                  {ev.replace('_', ' ')}
                </button>
              ))}
            </div>
          </div>
          <div className="col-span-2">
            <label className="text-xs text-base-content/50 mb-1 block">Username (optional)</label>
            <input className="input input-bordered input-sm w-full" value={form.username}
              onChange={e => setForm(f => ({ ...f, username: e.target.value }))} placeholder="Lucy C2" />
          </div>
        </div>

        <div className="flex justify-end gap-2 pt-2">
          <button onClick={onClose} className="btn btn-ghost btn-sm">Cancel</button>
          <button
            onClick={() => { if (form.name && form.url) { onSave(form); onClose() } }}
            className="btn btn-success btn-sm gap-1"
            disabled={!form.name || !form.url}
          >
            <Plus size={14}/> Add Webhook
          </button>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function Alerts() {
  const qc = useQueryClient()
  const [tab, setTab] = useState<'feed' | 'webhooks'>('feed')
  const [showModal, setShowModal] = useState(false)
  const [testingId, setTestingId] = useState<string | null>(null)

  const { data: alerts = [], refetch: refetchAlerts } = useQuery({
    queryKey: ['alerts'],
    queryFn: () => listAlerts({ limit: 200 }),
    refetchInterval: 10_000,
  })

  const { data: webhooks = [], refetch: refetchWebhooks } = useQuery({
    queryKey: ['webhooks'],
    queryFn: listWebhooks,
  })

  // Listen for live alert WS messages
  const { on } = useWebSocket()
  useEffect(() => {
    return on('alert', () => {
      qc.invalidateQueries({ queryKey: ['alerts'] })
    })
  }, [on, qc])

  const doMarkRead = useMutation({
    mutationFn: (id: string) => markRead([id]),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['alerts'] }),
  })

  const doMarkAll = useMutation({
    mutationFn: () => markRead(),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['alerts'] }),
  })

  const doAddWebhook = useMutation({
    mutationFn: (w: typeof EMPTY_HOOK) => addWebhook(w),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['webhooks'] }),
  })

  const doRemoveWebhook = useMutation({
    mutationFn: (id: string) => removeWebhook(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['webhooks'] }),
  })

  const handleTest = async (id: string) => {
    setTestingId(id)
    try { await testWebhook(id) } catch { /* ignore */ }
    setTestingId(null)
  }

  const unread = alerts.filter(a => !a.read).length

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-5">
      {showModal && (
        <WebhookModal
          onClose={() => setShowModal(false)}
          onSave={w => doAddWebhook.mutate(w)}
        />
      )}

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Bell size={24} className="text-yellow-400" />
            Alerts
            {unread > 0 && (
              <span className="badge badge-error badge-sm">{unread}</span>
            )}
          </h1>
          <p className="text-sm text-base-content/50 mt-1">Real-time events & webhook notifications</p>
        </div>
        <button onClick={() => { refetchAlerts(); refetchWebhooks() }} className="btn btn-ghost btn-sm gap-1">
          <RefreshCw size={14} /> Refresh
        </button>
      </div>

      {/* Tabs */}
      <div className="tabs tabs-boxed bg-base-200 w-fit">
        <button className={`tab ${tab === 'feed' ? 'tab-active' : ''}`} onClick={() => setTab('feed')}>
          Feed {unread > 0 && <span className="ml-1 badge badge-xs badge-error">{unread}</span>}
        </button>
        <button className={`tab ${tab === 'webhooks' ? 'tab-active' : ''}`} onClick={() => setTab('webhooks')}>
          Webhooks <span className="ml-1 badge badge-xs">{webhooks.length}</span>
        </button>
      </div>

      {/* Alert Feed */}
      {tab === 'feed' && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-sm text-base-content/50">{alerts.length} alerts · {unread} unread</span>
            {unread > 0 && (
              <button onClick={() => doMarkAll.mutate()} className="btn btn-ghost btn-xs gap-1">
                <CheckCheck size={13}/> Mark all read
              </button>
            )}
          </div>
          {alerts.length === 0 ? (
            <div className="text-center py-16 text-base-content/30">
              <BellOff size={40} className="mx-auto mb-3 opacity-30" />
              <p className="text-sm">No alerts yet. They'll appear here when agents connect or events occur.</p>
            </div>
          ) : (
            <div className="space-y-2 max-h-[70vh] overflow-y-auto pr-1">
              {alerts.map(a => (
                <AlertRow key={a.id} alert={a} onRead={id => doMarkRead.mutate(id)} />
              ))}
            </div>
          )}
        </div>
      )}

      {/* Webhooks */}
      {tab === 'webhooks' && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-sm text-base-content/50">{webhooks.length} webhook(s) configured</span>
            <button onClick={() => setShowModal(true)} className="btn btn-success btn-sm gap-1">
              <Plus size={14}/> Add Webhook
            </button>
          </div>
          {webhooks.length === 0 ? (
            <div className="text-center py-16 text-base-content/30">
              <Webhook size={40} className="mx-auto mb-3 opacity-30" />
              <p className="text-sm">No webhooks configured. Add one to receive Slack/Discord notifications.</p>
            </div>
          ) : (
            <div className="space-y-2">
              {webhooks.map(w => (
                <div key={w.id} className="flex items-center gap-3 bg-base-200 border border-base-300 rounded-lg px-4 py-3">
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-sm">{w.name}</p>
                    <p className="text-xs text-base-content/40 truncate">{w.url}</p>
                    <div className="flex gap-2 mt-1 flex-wrap">
                      <span className="badge badge-xs badge-outline">{w.kind}</span>
                      <span className="badge badge-xs">{w.min_severity}+</span>
                      {w.events.length > 0 && w.events.map(e => (
                        <span key={e} className="badge badge-xs badge-ghost">{e}</span>
                      ))}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <span className={`badge badge-xs ${w.enabled ? 'badge-success' : 'badge-ghost'}`}>
                      {w.enabled ? 'on' : 'off'}
                    </span>
                    <button
                      onClick={() => handleTest(w.id)}
                      disabled={testingId === w.id}
                      className="btn btn-ghost btn-xs gap-1"
                    >
                      {testingId === w.id
                        ? <Loader2 size={12} className="animate-spin" />
                        : <Send size={12} />}
                      Test
                    </button>
                    <button
                      onClick={() => doRemoveWebhook.mutate(w.id)}
                      className="btn btn-ghost btn-xs text-red-400"
                    >
                      <Trash2 size={12} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
