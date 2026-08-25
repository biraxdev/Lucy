import { useState } from 'react'
import { CheckCircle, Server, Shield, Zap, ChevronRight, X, Copy, Check } from 'lucide-react'
import api from '../api/client'

const STEPS = [
  { id: 1, title: 'Bienvenue', icon: Zap },
  { id: 2, title: 'Vérification système', icon: Server },
  { id: 3, title: 'Déployer un agent', icon: Shield },
]

interface HealthStatus {
  database: string
  redis: string
  backend: string
}

interface Props {
  onClose: () => void
}

export default function OnboardingWizard({ onClose }: Props) {
  const [step, setStep] = useState(1)
  const [health, setHealth] = useState<HealthStatus | null>(null)
  const [healthLoading, setHealthLoading] = useState(false)
  const [copied, setCopied] = useState(false)
  const [finishing, setFinishing] = useState(false)
  const c2Url = window.location.origin.replace('3000', '8000')

  const agentCmd = `# Option 1 — Python direct
python agent.py

# Option 2 — Binaire compilé (AgentBuilder)
# Dashboard → AgentBuilder → Build → Download → exécuter le .exe`

  const checkHealth = async () => {
    setHealthLoading(true)
    try {
      const res = await api.get('/setup/status')
      setHealth(res.data.health)
    } catch {
      setHealth({ database: 'error', redis: 'error', backend: 'ok' })
    } finally {
      setHealthLoading(false)
    }
  }

  const finish = async () => {
    setFinishing(true)
    try {
      await api.post('/setup/complete', { c2_url: c2Url, admin_password_changed: false })
    } catch { /* best effort */ }
    onClose()
  }

  const copyCmd = (text: string) => {
    navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const statusDot = (val?: string) => {
    if (!val) return <span className="text-gray-500">—</span>
    if (val === 'ok') return <span className="text-green-400">✓ OK</span>
    return <span className="text-red-400">✗ {val}</span>
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
      <div className="relative w-full max-w-2xl bg-gray-900 border border-gray-700 rounded-2xl shadow-2xl overflow-hidden">

        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-800">
          <div className="flex items-center gap-3">
            <span className="text-green-400 font-bold text-lg">Lucy C2</span>
            <span className="text-gray-500 text-sm">— Premier démarrage</span>
          </div>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-300 transition-colors">
            <X size={18} />
          </button>
        </div>

        {/* Step indicators */}
        <div className="flex items-center gap-0 px-6 pt-5 pb-2">
          {STEPS.map((s, i) => {
            const Icon = s.icon
            const active = step === s.id
            const done = step > s.id
            return (
              <div key={s.id} className="flex items-center flex-1">
                <div className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-all
                  ${active ? 'bg-green-500/20 text-green-400 border border-green-500/40' :
                    done ? 'text-green-500' : 'text-gray-600'}`}>
                  {done ? <CheckCircle size={16} /> : <Icon size={16} />}
                  <span className="hidden sm:inline">{s.title}</span>
                </div>
                {i < STEPS.length - 1 && (
                  <ChevronRight size={14} className="mx-1 text-gray-700 flex-shrink-0" />
                )}
              </div>
            )
          })}
        </div>

        {/* Content */}
        <div className="px-6 py-6 min-h-[300px]">

          {/* Step 1 — Welcome */}
          {step === 1 && (
            <div className="space-y-5">
              <div>
                <h2 className="text-2xl font-bold text-white mb-1">Bienvenue sur Lucy C2</h2>
                <p className="text-gray-400">Remote Agent Testing System — pour simulations Red Team autorisées.</p>
              </div>
              <div className="grid grid-cols-2 gap-3">
                {[
                  { icon: '🖥', title: 'Dashboard temps réel', desc: 'Tous tes agents, tâches et logs en un coup d\'œil.' },
                  { icon: '🔌', title: 'Modules dynamiques', desc: 'Keylog, screenshot, browser stealer, shell PTY...' },
                  { icon: '⚡', title: 'Timeline Builder', desc: 'Chaînes d\'attaque par drag & drop.' },
                  { icon: '📊', title: 'Reporting', desc: 'Rapports HTML/PDF générés automatiquement.' },
                ].map(f => (
                  <div key={f.title} className="bg-gray-800 rounded-xl p-4 border border-gray-700">
                    <div className="text-2xl mb-2">{f.icon}</div>
                    <div className="font-semibold text-white text-sm">{f.title}</div>
                    <div className="text-gray-400 text-xs mt-1">{f.desc}</div>
                  </div>
                ))}
              </div>
              <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-lg px-4 py-3 text-yellow-300 text-sm">
                ⚠️ Usage exclusivement sur des systèmes pour lesquels tu as une autorisation écrite.
              </div>
            </div>
          )}

          {/* Step 2 — Health check */}
          {step === 2 && (
            <div className="space-y-5">
              <div>
                <h2 className="text-xl font-bold text-white mb-1">Vérification système</h2>
                <p className="text-gray-400 text-sm">Vérifie que tous les services backend sont opérationnels.</p>
              </div>

              <div className="space-y-2">
                {[
                  { label: 'Backend (FastAPI)', key: 'backend' },
                  { label: 'Base de données (SQLite)', key: 'database' },
                  { label: 'Redis (Broker Celery)', key: 'redis' },
                ].map(item => (
                  <div key={item.key} className="flex items-center justify-between bg-gray-800 rounded-lg px-4 py-3 border border-gray-700">
                    <span className="text-gray-300 text-sm">{item.label}</span>
                    <span className="text-sm font-mono">
                      {healthLoading ? <span className="text-gray-500">vérification…</span>
                        : statusDot(health?.[item.key as keyof HealthStatus])}
                    </span>
                  </div>
                ))}
              </div>

              {!health && (
                <button
                  onClick={checkHealth}
                  disabled={healthLoading}
                  className="w-full bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded-lg py-2.5 text-sm font-medium transition-colors"
                >
                  {healthLoading ? 'Vérification…' : 'Lancer la vérification'}
                </button>
              )}

              {health && health.database !== 'ok' && (
                <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-3 text-red-300 text-sm">
                  La base de données n'est pas accessible. Vérifie que le backend est bien démarré.
                </div>
              )}
              {health && health.redis !== 'ok' && (
                <div className="bg-orange-500/10 border border-orange-500/30 rounded-lg px-4 py-3 text-orange-300 text-sm">
                  Redis n'est pas accessible. Le task queue (Celery) ne fonctionnera pas.
                  Lance : <code className="bg-gray-800 px-1 rounded">docker-compose up redis</code>
                </div>
              )}
            </div>
          )}

          {/* Step 3 — Deploy agent */}
          {step === 3 && (
            <div className="space-y-5">
              <div>
                <h2 className="text-xl font-bold text-white mb-1">Déployer un agent</h2>
                <p className="text-gray-400 text-sm">Exécute l'implant sur la machine cible pour qu'il apparaisse dans le Dashboard.</p>
              </div>

              <div className="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
                <div className="flex items-center justify-between px-4 py-2 border-b border-gray-700 bg-gray-900">
                  <span className="text-gray-400 text-xs font-mono">Commandes</span>
                  <button
                    onClick={() => copyCmd(agentCmd)}
                    className="flex items-center gap-1 text-gray-400 hover:text-white text-xs transition-colors"
                  >
                    {copied ? <><Check size={12} className="text-green-400" /> Copié</> : <><Copy size={12} /> Copier</>}
                  </button>
                </div>
                <pre className="px-4 py-4 text-green-300 text-sm font-mono whitespace-pre-wrap">{agentCmd}</pre>
              </div>

              <div className="bg-gray-800 rounded-xl border border-gray-700 p-4 space-y-2">
                <div className="text-gray-300 text-sm font-semibold mb-2">URL C2 détectée</div>
                <div className="font-mono text-green-400 text-sm bg-gray-900 rounded px-3 py-2">{c2Url}</div>
                <p className="text-gray-500 text-xs">L'agent doit pouvoir joindre cette adresse depuis la machine cible.</p>
              </div>

              <div className="text-sm text-gray-400">
                💡 Pour un binaire autonome (.exe / .bin) sans Python requis → <span className="text-blue-400">Dashboard → AgentBuilder</span>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-6 py-4 border-t border-gray-800 bg-gray-900/50">
          <button
            onClick={() => setStep(s => Math.max(1, s - 1))}
            disabled={step === 1}
            className="px-4 py-2 text-sm text-gray-400 hover:text-white disabled:opacity-0 transition-colors"
          >
            ← Retour
          </button>

          <div className="flex gap-1.5">
            {STEPS.map(s => (
              <div key={s.id} className={`w-2 h-2 rounded-full transition-colors ${step === s.id ? 'bg-green-400' : step > s.id ? 'bg-green-700' : 'bg-gray-700'}`} />
            ))}
          </div>

          {step < 3 ? (
            <button
              onClick={() => { setStep(s => s + 1); if (step === 1) checkHealth() }}
              className="px-5 py-2 bg-green-600 hover:bg-green-500 text-white rounded-lg text-sm font-medium transition-colors flex items-center gap-1.5"
            >
              Suivant <ChevronRight size={16} />
            </button>
          ) : (
            <button
              onClick={finish}
              disabled={finishing}
              className="px-5 py-2 bg-green-600 hover:bg-green-500 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition-colors flex items-center gap-1.5"
            >
              <CheckCircle size={16} /> Terminer
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
