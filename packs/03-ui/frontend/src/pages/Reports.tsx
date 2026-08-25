import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import {
  FileText, Download, RefreshCw, PlusCircle, AlertTriangle,
  CheckCircle, Clock, Loader2, Shield, Key, Terminal, Bug,
  FileJson, FileType, Sparkles, ChevronRight,
} from 'lucide-react'
import { generateReport, listReports, getReport, downloadReport } from '../api/reports'
import type { ReportRequest, Report } from '../api/reports'
import { Card } from '../components/ui/Card'
import { PageTransition } from '../components/ui/PageTransition'

const TYPE_OPTIONS = [
  { value: 'engagement',  label: 'Engagement',  icon: Shield,   desc: 'Full red team: agents, findings, credentials, task log', gradient: 'from-emerald-500/15 to-transparent', accent: 'text-emerald-400' },
  { value: 'credentials', label: 'Credentials', icon: Key,      desc: 'All harvested passwords, cookies, WiFi, env secrets',    gradient: 'from-rose-500/15 to-transparent',   accent: 'text-rose-400' },
  { value: 'technical',   label: 'Technical',   icon: Terminal, desc: 'Task execution log, agent detail, event logs',           gradient: 'from-sky-500/15 to-transparent',    accent: 'text-sky-400' },
  { value: 'findings',    label: 'Findings',    icon: Bug,      desc: 'Manual & auto findings with severity & recommendations', gradient: 'from-amber-500/15 to-transparent',  accent: 'text-amber-400' },
] as const

const FORMAT_OPTIONS = [
  { value: 'html', label: 'HTML', icon: FileType, color: 'text-blue-400',  bg: 'bg-blue-500/10',  border: 'border-blue-500/30' },
  { value: 'pdf',  label: 'PDF',  icon: FileText, color: 'text-red-400',   bg: 'bg-red-500/10',   border: 'border-red-500/30' },
  { value: 'json', label: 'JSON', icon: FileJson, color: 'text-amber-400', bg: 'bg-amber-500/10', border: 'border-amber-500/30' },
] as const

function StatusBadge({ status }: { status: Report['status'] }) {
  if (status === 'done')     return <span className="flex items-center gap-1 text-emerald-400 text-xs font-bold"><CheckCircle size={13}/> Done</span>
  if (status === 'error')    return <span className="flex items-center gap-1 text-rose-400 text-xs font-bold"><AlertTriangle size={13}/> Error</span>
  if (status === 'building') return <span className="flex items-center gap-1 text-sky-400 text-xs font-bold"><Loader2 size={13} className="animate-spin"/> Building…</span>
  return <span className="flex items-center gap-1 text-base-content/50 text-xs font-bold"><Clock size={13}/> Queued</span>
}

function ReportCard({ report, onPoll }: { report: Report; onPoll: (id: string) => void }) {
  const isBuilding = report.status === 'building' || report.status === 'queued'
  useEffect(() => {
    if (!isBuilding) return
    const t = setInterval(() => onPoll(report.report_id), 2000)
    return () => clearInterval(t)
  }, [isBuilding, report.report_id, onPoll])

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, x: -20 }}
    >
      <Card hover={false} className="p-4">
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-10 h-10 rounded-xl bg-base-300 flex items-center justify-center shrink-0">
              <FileText size={18} className="text-base-content/50" />
            </div>
            <div className="min-w-0">
              <p className="text-sm font-mono text-base-content truncate">{report.report_id.slice(0, 12)}…</p>
              {report.error && <p className="text-xs text-rose-400 mt-0.5 truncate">{report.error}</p>}
            </div>
          </div>
          <div className="flex items-center gap-3 shrink-0">
            <StatusBadge status={report.status} />
            <AnimatePresence>
              {report.status === 'done' && (
                <motion.button
                  initial={{ opacity: 0, scale: 0.8 }}
                  animate={{ opacity: 1, scale: 1 }}
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                  onClick={() => downloadReport(report.report_id)}
                  className="btn btn-xs btn-success gap-1"
                >
                  <Download size={12} /> Export
                </motion.button>
              )}
            </AnimatePresence>
          </div>
        </div>
      </Card>
    </motion.div>
  )
}

export default function Reports() {
  const qc = useQueryClient()
  const [type, setType]     = useState<ReportRequest['type']>('engagement')
  const [format, setFormat] = useState<ReportRequest['format']>('html')

  const { data: reports = [], refetch } = useQuery({
    queryKey: ['reports'],
    queryFn: listReports,
    refetchInterval: false,
  })

  const generate = useMutation({
    mutationFn: (body: ReportRequest) => generateReport(body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['reports'] }),
  })

  const pollReport = async (id: string) => {
    try {
      const r = await getReport(id)
      qc.setQueryData<Report[]>(['reports'], (prev = []) =>
        prev.map(p => p.report_id === id ? { ...p, ...r } : p)
      )
    } catch { /* ignore */ }
  }

  const handleGenerate = () => generate.mutate({ type, format })
  const activeType = TYPE_OPTIONS.find(t => t.value === type)!
  const activeFormat = FORMAT_OPTIONS.find(f => f.value === format)!

  return (
    <PageTransition>
      <div className="page-container max-w-5xl space-y-6">
        {/* Header */}
        <div className="flex items-end justify-between">
          <div className="space-y-1">
            <h1 className="text-2xl font-bold flex items-center gap-2">
              <FileText size={24} className="text-success" /> Reports
            </h1>
            <p className="text-sm text-base-content/50">Generate & export engagement reports in one click.</p>
          </div>
          <button onClick={() => refetch()} className="btn btn-sm btn-ghost gap-1">
            <RefreshCw size={14} /> Refresh
          </button>
        </div>

        {/* === Generate panel === */}
        <Card hover={false} className="p-5 space-y-5">
          <h2 className="text-sm font-bold uppercase tracking-wider text-base-content/50 flex items-center gap-2">
            <Sparkles size={14} className="text-success" /> New Report
          </h2>

          {/* Type selector — visual cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            {TYPE_OPTIONS.map(opt => {
              const Icon = opt.icon
              const isActive = type === opt.value
              return (
                <motion.button
                  key={opt.value}
                  whileHover={{ y: -3 }}
                  whileTap={{ scale: 0.97 }}
                  onClick={() => setType(opt.value)}
                  className={`relative text-left rounded-xl border-2 p-4 overflow-hidden transition-all ${
                    isActive ? 'border-success shadow-md' : 'border-base-300 hover:border-base-content/20'
                  }`}
                >
                  <div className={`absolute inset-0 bg-gradient-to-br ${opt.gradient} ${isActive ? 'opacity-100' : 'opacity-30'}`} />
                  <div className="relative z-10 space-y-2">
                    <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${opt.accent} bg-base-200/50`}>
                      <Icon size={18} />
                    </div>
                    <p className="font-semibold text-sm">{opt.label}</p>
                    <p className="text-[11px] text-base-content/50 leading-snug">{opt.desc}</p>
                  </div>
                  {isActive && (
                    <motion.div
                      initial={{ scale: 0 }}
                      animate={{ scale: 1 }}
                      className="absolute top-2 right-2 w-5 h-5 rounded-full bg-success text-base-100 flex items-center justify-center z-20"
                    >
                      <CheckCircle size={12} />
                    </motion.div>
                  )}
                </motion.button>
              )
            })}
          </div>

          {/* Format selector — pill badges */}
          <div className="flex items-center gap-3 pt-2 border-t border-base-300/50">
            <span className="text-xs text-base-content/50 w-16">Format</span>
            <div className="flex gap-2">
              {FORMAT_OPTIONS.map(f => {
                const Icon = f.icon
                const isActive = format === f.value
                return (
                  <button
                    key={f.value}
                    onClick={() => setFormat(f.value)}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all ${
                      isActive ? `${f.bg} ${f.color} ${f.border}` : 'border-base-300 text-base-content/50 hover:border-base-content/20'
                    }`}
                  >
                    <Icon size={13} /> {f.label}
                  </button>
                )
              })}
            </div>
          </div>

          {/* Summary + Generate */}
          <div className="flex items-center justify-between pt-2 border-t border-base-300/50">
            <p className="text-xs text-base-content/50 flex items-center gap-2">
              <span className={`font-bold ${activeType.accent}`}>{activeType.label}</span>
              <ChevronRight size={12} className="text-base-content/30" />
              <span className={`font-bold ${activeFormat.color}`}>{activeFormat.label}</span>
              <ChevronRight size={12} className="text-base-content/30" />
              <span>All agents</span>
            </p>
            <motion.button
              whileHover={{ scale: 1.03 }}
              whileTap={{ scale: 0.97 }}
              onClick={handleGenerate}
              disabled={generate.isPending}
              className="btn btn-success btn-sm gap-2"
            >
              {generate.isPending
                ? <Loader2 size={14} className="animate-spin" />
                : <PlusCircle size={14} />}
              Generate Report
            </motion.button>
          </div>
        </Card>

        {/* === Report list === */}
        <section className="space-y-3">
          <h2 className="text-sm font-bold uppercase tracking-wider text-base-content/50 flex items-center gap-2">
            Generated Reports
            <span className="badge badge-sm badge-ghost">{reports.length}</span>
          </h2>
          {reports.length === 0 ? (
            <div className="text-center py-16 text-base-content/30 space-y-3">
              <FileText size={40} className="mx-auto opacity-30" />
              <p className="text-sm">No reports yet.</p>
              <p className="text-xs">Generate your first one above — it takes a few seconds.</p>
            </div>
          ) : (
            <div className="space-y-2">
              <AnimatePresence>
                {[...reports].reverse().map(r => (
                  <ReportCard key={r.report_id} report={r} onPoll={pollReport} />
                ))}
              </AnimatePresence>
            </div>
          )}
        </section>
      </div>
    </PageTransition>
  )
}
