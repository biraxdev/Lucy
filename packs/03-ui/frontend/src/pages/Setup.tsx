import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { CheckCircle, XCircle, Loader2, RefreshCw, Terminal, Package, Server, Database, Zap, Copy, Check, RotateCcw } from 'lucide-react'
import api from '../api/client'

interface HealthData {
  setup_complete: boolean
  completed_at: string | null
  health: {
    database: string
    redis: string
    backend: string
  }
}

export default function Setup() {
  const [copied, setCopied] = useState<string | null>(null)

  const { data, isLoading, refetch, isFetching } = useQuery<HealthData>({
    queryKey: ['setup-status'],
    queryFn: async () => (await api.get('/setup/status')).data,
    refetchInterval: 10000,
  })

  const resetMutation = useMutation({
    mutationFn: () => api.post('/setup/reset'),
    onSuccess: () => refetch(),
  })

  const copy = (text: string, key: string) => {
    navigator.clipboard.writeText(text)
    setCopied(key)
    setTimeout(() => setCopied(null), 2000)
  }

  const c2Url = window.location.origin.replace(':3000', ':8000')

  const StatusIcon = ({ val }: { val?: string }) => {
    if (!val) return <Loader2 size={16} className="animate-spin text-gray-500" />
    if (val === 'ok') return <CheckCircle size={16} className="text-green-400" />
    return <XCircle size={16} className="text-red-400" />
  }

  const StatusText = ({ val }: { val?: string }) => {
    if (!val) return <span className="text-gray-500 text-sm">—</span>
    if (val === 'ok') return <span className="text-green-400 text-sm font-medium">Opérationnel</span>
    return <span className="text-red-400 text-sm">{val}</span>
  }

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Zap size={24} className="text-green-400" /> Setup & Onboarding
          </h1>
          <p className="text-gray-400 mt-1">Vue d'ensemble de la santé du système et guide de démarrage.</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => refetch()}
            disabled={isFetching}
            className="flex items-center gap-1.5 px-3 py-2 bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-lg text-sm transition-colors"
          >
            <RefreshCw size={14} className={isFetching ? 'animate-spin' : ''} />
            Actualiser
          </button>
          <button
            onClick={() => resetMutation.mutate()}
            className="flex items-center gap-1.5 px-3 py-2 bg-gray-800 hover:bg-red-900/40 text-gray-400 hover:text-red-400 rounded-lg text-sm transition-colors"
          >
            <RotateCcw size={14} /> Reset wizard
          </button>
        </div>
      </div>

      {/* Setup complete banner */}
      {data?.setup_complete && (
        <div className="bg-green-500/10 border border-green-500/30 rounded-xl px-5 py-4 flex items-center gap-3">
          <CheckCircle size={20} className="text-green-400 flex-shrink-0" />
          <div>
            <div className="text-green-300 font-semibold">Setup complété</div>
            <div className="text-green-400/70 text-sm">
              {data.completed_at ? `Le ${new Date(data.completed_at).toLocaleString('fr-FR')}` : ''}
            </div>
          </div>
        </div>
      )}

      {/* System Health */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
        <div className="px-5 py-3 border-b border-gray-800 flex items-center gap-2">
          <Server size={16} className="text-blue-400" />
          <span className="font-semibold text-white">Santé du système</span>
        </div>
        <div className="divide-y divide-gray-800">
          {isLoading ? (
            <div className="px-5 py-8 flex justify-center">
              <Loader2 size={24} className="animate-spin text-gray-500" />
            </div>
          ) : (
            [
              { key: 'backend', label: 'Backend FastAPI', desc: 'Serveur HTTP + WebSocket' },
              { key: 'database', label: 'Base de données SQLite', desc: 'Stockage agents, tâches, credentials' },
              { key: 'redis', label: 'Redis', desc: 'Broker Celery + cache' },
            ].map(item => (
              <div key={item.key} className="flex items-center justify-between px-5 py-4">
                <div>
                  <div className="text-white text-sm font-medium">{item.label}</div>
                  <div className="text-gray-500 text-xs">{item.desc}</div>
                </div>
                <div className="flex items-center gap-2">
                  <StatusText val={data?.health?.[item.key as keyof typeof data.health]} />
                  <StatusIcon val={data?.health?.[item.key as keyof typeof data.health]} />
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Redis error hint */}
      {data?.health?.redis !== 'ok' && data?.health?.redis && (
        <div className="bg-orange-500/10 border border-orange-500/30 rounded-xl p-4 space-y-2">
          <div className="text-orange-300 font-semibold text-sm">Redis non disponible</div>
          <p className="text-orange-200/70 text-sm">Lance Redis avec Docker :</p>
          <CodeBlock text="docker-compose up redis -d" id="redis-cmd" copied={copied} onCopy={copy} />
        </div>
      )}

      {/* Quick Start */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
        <div className="px-5 py-3 border-b border-gray-800 flex items-center gap-2">
          <Terminal size={16} className="text-green-400" />
          <span className="font-semibold text-white">Déployer un premier agent</span>
        </div>
        <div className="p-5 space-y-4">

          <div>
            <div className="text-gray-300 text-sm font-medium mb-2">Option A — Python direct (machine avec Python 3.12)</div>
            <CodeBlock text="cd agent && python agent.py" id="opt-a" copied={copied} onCopy={copy} />
          </div>

          <div>
            <div className="text-gray-300 text-sm font-medium mb-2">Option B — Binaire compilé (sans Python requis)</div>
            <div className="bg-gray-800 rounded-lg px-4 py-3 text-gray-300 text-sm space-y-1">
              <div>1. Va dans <span className="text-blue-400 font-mono">Dashboard → AgentBuilder</span></div>
              <div>2. Configure l'URL C2, les modules, l'OS cible</div>
              <div>3. Clique <strong>Build</strong> → <strong>Download .exe</strong></div>
              <div>4. Copie le binaire sur la machine cible et exécute-le</div>
            </div>
          </div>

          <div>
            <div className="text-gray-300 text-sm font-medium mb-2">URL C2 (à embarquer dans l'agent)</div>
            <CodeBlock text={c2Url} id="c2url" copied={copied} onCopy={copy} />
          </div>
        </div>
      </div>

      {/* Docker full stack */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
        <div className="px-5 py-3 border-b border-gray-800 flex items-center gap-2">
          <Package size={16} className="text-purple-400" />
          <span className="font-semibold text-white">Démarrage complet (Docker)</span>
        </div>
        <div className="p-5 space-y-3">
          <p className="text-gray-400 text-sm">Lance tout le stack (backend + frontend + redis + celery) en une commande :</p>
          <CodeBlock text="make dev" id="make-dev" copied={copied} onCopy={copy} />
          <div className="grid grid-cols-2 gap-3 text-sm">
            {[
              { cmd: 'make build', desc: 'Build les images Docker' },
              { cmd: 'make logs', desc: 'Tail les logs' },
              { cmd: 'make test', desc: 'Lance les tests pytest' },
              { cmd: 'make reset', desc: 'Reset la DB + rapports' },
            ].map(item => (
              <div key={item.cmd} className="bg-gray-800 rounded-lg px-3 py-2 flex items-center justify-between">
                <code className="text-green-400 text-xs">{item.cmd}</code>
                <span className="text-gray-500 text-xs">{item.desc}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* API keys */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
        <div className="px-5 py-3 border-b border-gray-800 flex items-center gap-2">
          <Database size={16} className="text-yellow-400" />
          <span className="font-semibold text-white">Credentials par défaut</span>
        </div>
        <div className="p-5 space-y-3">
          <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-3 text-red-300 text-sm">
            ⚠️ Change le mot de passe admin et toutes les clés secrètes dans <code>.env</code> avant toute utilisation en production.
          </div>
          <table className="w-full text-sm">
            <tbody className="divide-y divide-gray-800">
              {[
                { label: 'Username', value: 'admin' },
                { label: 'Password par défaut', value: 'admin' },
                { label: 'Route admin', value: 'http://localhost:3000' },
                { label: 'API backend', value: 'http://localhost:8000' },
                { label: 'Docs API', value: 'http://localhost:8000/docs' },
              ].map(row => (
                <tr key={row.label}>
                  <td className="py-2 pr-4 text-gray-500">{row.label}</td>
                  <td className="py-2 font-mono text-gray-300">{row.value}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

    </div>
  )
}

function CodeBlock({ text, id, copied, onCopy }: { text: string, id: string, copied: string | null, onCopy: (t: string, id: string) => void }) {
  return (
    <div className="bg-gray-800 rounded-lg border border-gray-700 flex items-center justify-between px-4 py-2.5">
      <code className="text-green-300 text-sm font-mono">{text}</code>
      <button onClick={() => onCopy(text, id)} className="ml-3 text-gray-500 hover:text-white transition-colors flex-shrink-0">
        {copied === id ? <Check size={14} className="text-green-400" /> : <Copy size={14} />}
      </button>
    </div>
  )
}
