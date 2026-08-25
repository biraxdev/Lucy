import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Shield, RefreshCw, AlertTriangle, Activity, ScanLine,
  FileCheck, Cpu, CheckCircle, Eye, EyeOff,
} from 'lucide-react'
import {
  getDefenseStatus,
  listDefenseAlerts,
  listDefenseRules,
  listScanners,
  runLocalScanner,
  markDefenseAlertRead,
  markAllDefenseAlertsRead,
  type DefenseAlert,
  type DefenseRule,
  type ScannerInfo,
} from '../api/defense'
import { Card, CardMetric } from '../components/ui/Card'
import { PageTransition } from '../components/ui/PageTransition'
import { StatusBadge } from '../components/ui/StatusBadge'

const severityColor: Record<string, string> = {
  critical: 'bg-red-500/20 text-red-400 border-red-500/30',
  high: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
  medium: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  low: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  info: 'bg-base-300 text-base-content/70',
}

export default function Defense() {
  const qc = useQueryClient()
  const [selectedScanner, setSelectedScanner] = useState('')
  const [scanParams, setScanParams] = useState('{}')
  const [activeTab, setActiveTab] = useState<'alerts' | 'rules' | 'scanners'>('alerts')
  const [showRead, setShowRead] = useState(false)

  const { data: status, isLoading: statusLoading, refetch: refetchStatus } = useQuery({
    queryKey: ['defense-status'],
    queryFn: getDefenseStatus,
    refetchInterval: 10_000,
  })

  const { data: alerts = [], refetch: refetchAlerts } = useQuery({
    queryKey: ['defense-alerts'],
    queryFn: () => listDefenseAlerts({ limit: 100 }),
    refetchInterval: 10_000,
  })

  const { data: rules = [] } = useQuery({
    queryKey: ['defense-rules'],
    queryFn: listDefenseRules,
  })

  const { data: scanners = [] } = useQuery({
    queryKey: ['defense-scanners'],
    queryFn: listScanners,
  })

  const markRead = useMutation({
    mutationFn: markDefenseAlertRead,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['defense-alerts'] }),
  })

  const markAllRead = useMutation({
    mutationFn: markAllDefenseAlertsRead,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['defense-alerts'] }),
  })

  const runScan = useMutation({
    mutationFn: () => {
      let params: Record<string, unknown> = {}
      try {
        params = JSON.parse(scanParams)
      } catch { /* empty */ }
      return runLocalScanner(selectedScanner, 'scan', params)
    },
    onSuccess: () => {
      refetchStatus()
      setSelectedScanner('')
    },
  })

  const filteredAlerts = showRead ? alerts : alerts.filter((a: DefenseAlert) => !a.read)

  return (
    <PageTransition>
      <div className="page-container space-y-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Shield className="text-success" size={28} />
            <div>
              <h1 className="text-2xl font-bold">Defense Center</h1>
              <p className="text-sm text-base-content/60">SIEM ingestion, detection rules, and authorized scanners.</p>
            </div>
          </div>
          <button className="btn btn-sm btn-outline gap-2" onClick={() => { refetchStatus(); refetchAlerts() }}>
            <RefreshCw size={14} /> Refresh
          </button>
        </div>

        {statusLoading ? (
          <div className="py-10 text-center text-base-content/40">Loading defense status…</div>
        ) : (
          <section className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <Card className="p-5" hover>
              <CardMetric value={status?.stats.events_ingested ?? 0} label="Events Ingested" trend="total telemetry" />
            </Card>
            <Card className="p-5" hover>
              <CardMetric value={status?.stats.alerts_generated ?? 0} label="Alerts Generated" trend={`${status?.stats.unread_alerts ?? 0} unread`} color="text-warning" />
            </Card>
            <Card className="p-5" hover>
              <CardMetric value={status?.stats.rules_active ?? 0} label="Active Rules" trend="MITRE mapped" color="text-info" />
            </Card>
            <Card className="p-5" hover>
              <CardMetric value={status?.stats.by_severity.critical ?? 0} label="Critical Alerts" trend="needs review" color="text-error" />
            </Card>
          </section>
        )}

        <div className="tabs tabs-boxed bg-base-200 w-fit">
          {(['alerts', 'rules', 'scanners'] as const).map((tab) => (
            <button
              key={tab}
              className={`tab ${activeTab === tab ? 'tab-active' : ''}`}
              onClick={() => setActiveTab(tab)}
            >
              {tab === 'alerts' && <><AlertTriangle size={14} className="mr-1" /> Alerts</>}
              {tab === 'rules' && <><Activity size={14} className="mr-1" /> Rules</>}
              {tab === 'scanners' && <><ScanLine size={14} className="mr-1" /> Scanners</>}
            </button>
          ))}
        </div>

        {activeTab === 'alerts' && (
          <section className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-bold flex items-center gap-2"><AlertTriangle size={18} /> Detection Alerts</h2>
              <div className="flex gap-2">
                <button className="btn btn-xs btn-ghost gap-1" onClick={() => setShowRead((s) => !s)}>
                  {showRead ? <EyeOff size={12} /> : <Eye size={12} />} {showRead ? 'Hide read' : 'Show read'}
                </button>
                <button className="btn btn-xs btn-success gap-1" onClick={() => markAllRead.mutate()}>
                  <CheckCircle size={12} /> Mark all read
                </button>
              </div>
            </div>
            <div className="overflow-x-auto rounded-lg border border-base-300">
              <table className="table table-sm">
                <thead className="bg-base-200">
                  <tr>
                    <th>Severity</th>
                    <th>Rule</th>
                    <th>Host</th>
                    <th>MITRE</th>
                    <th>Time</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredAlerts.map((alert: DefenseAlert) => (
                    <tr key={alert.id} className={alert.read ? 'opacity-50' : ''}>
                      <td><span className={`badge badge-sm ${severityColor[alert.severity] ?? severityColor.info}`}>{alert.severity}</span></td>
                      <td>{alert.rule_name}</td>
                      <td className="font-mono text-xs">{alert.hostname}</td>
                      <td className="font-mono text-xs">{alert.mitre || '—'}</td>
                      <td className="text-xs">{new Date(alert.timestamp).toLocaleString()}</td>
                      <td>
                        {!alert.read && (
                          <button className="btn btn-xs btn-ghost" onClick={() => markRead.mutate(alert.id)}>
                            <CheckCircle size={12} />
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                  {filteredAlerts.length === 0 && (
                    <tr><td colSpan={6} className="text-center text-base-content/40 py-6">No alerts.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </section>
        )}

        {activeTab === 'rules' && (
          <section className="space-y-4">
            <h2 className="text-lg font-bold flex items-center gap-2"><Activity size={18} /> Detection Rules</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {rules.map((rule: DefenseRule) => (
                <div key={rule.id} className="card bg-base-200 border border-base-300 p-4 space-y-2">
                  <div className="flex items-start justify-between">
                    <h3 className="font-semibold">{rule.name}</h3>
                    <StatusBadge status={rule.enabled ? 'online' : 'offline'} />
                  </div>
                  <p className="text-sm text-base-content/60">{rule.description}</p>
                  <div className="flex gap-2 text-xs font-mono">
                    <span className="badge badge-sm badge-outline">{rule.mitre || '—'}</span>
                    <span className={`badge badge-sm ${severityColor[rule.severity]}`}>{rule.severity}</span>
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}

        {activeTab === 'scanners' && (
          <section className="space-y-4">
            <h2 className="text-lg font-bold flex items-center gap-2"><ScanLine size={18} /> Authorized Scanners</h2>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <div className="card bg-base-200 border border-base-300 p-4 space-y-3">
                <label className="form-control w-full">
                  <span className="label-text">Scanner</span>
                  <select
                    className="select select-bordered select-sm w-full"
                    value={selectedScanner}
                    onChange={(e) => setSelectedScanner(e.target.value)}
                  >
                    <option value="">Choose…</option>
                    {scanners.map((s: ScannerInfo) => (
                      <option key={s.id} value={s.id}>{s.name} — {s.description}</option>
                    ))}
                  </select>
                </label>
                <label className="form-control w-full">
                  <span className="label-text">Parameters (JSON)</span>
                  <textarea
                    className="textarea textarea-bordered textarea-sm w-full font-mono"
                    rows={4}
                    value={scanParams}
                    onChange={(e) => setScanParams(e.target.value)}
                    placeholder='{"host":"127.0.0.1","ports":[22,80,443]}'
                  />
                </label>
                <button
                  className="btn btn-success btn-sm gap-2"
                  disabled={!selectedScanner || runScan.isPending}
                  onClick={() => runScan.mutate()}
                >
                  <ScanLine size={14} /> Run Scan
                </button>
                {runScan.isSuccess && (
                  <pre className="bg-base-300 rounded p-3 text-xs overflow-auto max-h-60">
                    {JSON.stringify(runScan.data, null, 2)}
                  </pre>
                )}
              </div>

              <div className="grid grid-cols-1 gap-3">
                {scanners.map((s: ScannerInfo) => (
                  <div key={s.id} className="flex items-center gap-3 p-3 bg-base-200 rounded-lg border border-base-300">
                    {s.id.includes('integrity') ? <FileCheck size={18} className="text-info" /> : s.id.includes('process') ? <Cpu size={18} className="text-warning" /> : <ScanLine size={18} className="text-success" />}
                    <div>
                      <div className="font-medium">{s.name}</div>
                      <div className="text-xs text-base-content/60">{s.description}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </section>
        )}
      </div>
    </PageTransition>
  )
}
