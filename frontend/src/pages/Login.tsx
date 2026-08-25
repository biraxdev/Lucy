import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ShieldAlert, Loader2, Zap, Lock, User } from 'lucide-react'
import { motion } from 'framer-motion'
import { login, me } from '../api/auth'
import { useAuthStore } from '../stores/authStore'

/* Animated background particles */
function Particles() {
  const particles = Array.from({ length: 20 }, (_, i) => ({
    id: i,
    size: Math.random() * 4 + 2,
    left: `${Math.random() * 100}%`,
    top: `${Math.random() * 100}%`,
    delay: `${Math.random() * 5}s`,
    duration: `${Math.random() * 10 + 10}s`,
  }))
  return (
    <div className="fixed inset-0 overflow-hidden pointer-events-none z-0">
      {particles.map((p) => (
        <div
          key={p.id}
          className="absolute rounded-full opacity-20"
          style={{
            width: p.size,
            height: p.size,
            left: p.left,
            top: p.top,
            background: p.id % 3 === 0 ? '#00ff9d' : p.id % 3 === 1 ? '#00e5ff' : '#b829dd',
            animation: `float-particle ${p.duration} ease-in-out ${p.delay} infinite`,
          }}
        />
      ))}
    </div>
  )
}

export default function Login() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const { setTokens, setUser } = useAuthStore()
  const navigate = useNavigate()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      const tokens = await login(username, password)
      setTokens(tokens.access_token, tokens.refresh_token)
      const user = await me()
      setUser(user)
      navigate('/')
    } catch {
      setError('Invalid credentials')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center relative overflow-hidden mesh-gradient">
      <Particles />

      {/* Grid pattern overlay */}
      <div className="absolute inset-0 grid-pattern opacity-50 pointer-events-none z-0" />

      {/* Animated gradient orbs */}
      <div className="absolute top-[-20%] left-[-10%] w-[600px] h-[600px] rounded-full bg-[radial-gradient(circle,rgba(0,255,157,0.12)_0%,transparent_70%)] blur-3xl animate-float pointer-events-none z-0" />
      <div className="absolute bottom-[-20%] right-[-10%] w-[500px] h-[500px] rounded-full bg-[radial-gradient(circle,rgba(0,229,255,0.10)_0%,transparent_70%)] blur-3xl animate-float pointer-events-none z-0" style={{ animationDelay: '3s' }} />

      <motion.div
        initial={{ opacity: 0, y: 30, scale: 0.95 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.6, ease: 'easeOut' }}
        className="relative z-10 w-full max-w-md mx-4"
      >
        {/* Gradient border wrapper */}
        <div className="relative rounded-2xl p-[1px] gradient-border">
          <div className="relative rounded-2xl bg-base-100/90 backdrop-blur-2xl border border-white/5 shadow-2xl shadow-success/5 overflow-hidden">
            {/* Top glow line */}
            <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-success/40 to-transparent" />

            <div className="px-8 py-10 space-y-8">
              {/* Brand header */}
              <div className="flex flex-col items-center gap-4">
                <motion.div
                  initial={{ scale: 0.8, opacity: 0 }}
                  animate={{ scale: 1, opacity: 1 }}
                  transition={{ delay: 0.2, duration: 0.5 }}
                  className="relative"
                >
                  <div className="absolute inset-0 rounded-2xl bg-success/20 blur-xl animate-pulse-glow" />
                  <div className="relative p-4 rounded-2xl bg-success/10 border border-success/20">
                    <ShieldAlert size={36} className="text-success" strokeWidth={1.5} />
                  </div>
                </motion.div>

                <div className="text-center space-y-1">
                  <motion.h1
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.3 }}
                    className="text-3xl font-bold tracking-tight gradient-text"
                  >
                    Lucy
                  </motion.h1>
                  <motion.p
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: 0.4 }}
                    className="text-xs font-mono text-base-content/40 tracking-widest uppercase"
                  >
                    Remote Agent Testing System
                  </motion.p>
                </div>
              </div>

              <form onSubmit={handleSubmit} className="space-y-5">
                <motion.div
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.4 }}
                  className="space-y-2"
                >
                  <label className="text-xs font-medium text-base-content/60 uppercase tracking-wider flex items-center gap-1.5">
                    <User size={12} className="text-success/60" /> Username
                  </label>
                  <div className="relative">
                    <input
                      className="input w-full bg-base-200/50 border-base-300/50 focus:border-success/50 focus:ring-2 focus:ring-success/10 rounded-xl text-sm placeholder:text-base-content/30 transition-all"
                      placeholder="Enter your username"
                      value={username}
                      onChange={(e) => setUsername(e.target.value)}
                      autoFocus
                      required
                    />
                    <div className="absolute inset-0 rounded-xl pointer-events-none ring-1 ring-inset ring-white/5" />
                  </div>
                </motion.div>

                <motion.div
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.5 }}
                  className="space-y-2"
                >
                  <label className="text-xs font-medium text-base-content/60 uppercase tracking-wider flex items-center gap-1.5">
                    <Lock size={12} className="text-success/60" /> Password
                  </label>
                  <div className="relative">
                    <input
                      type="password"
                      className="input w-full bg-base-200/50 border-base-300/50 focus:border-success/50 focus:ring-2 focus:ring-success/10 rounded-xl text-sm placeholder:text-base-content/30 transition-all"
                      placeholder="Enter your password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      required
                    />
                    <div className="absolute inset-0 rounded-xl pointer-events-none ring-1 ring-inset ring-white/5" />
                  </div>
                </motion.div>

                {error && (
                  <motion.p
                    initial={{ opacity: 0, y: -5 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="text-error text-sm flex items-center gap-1.5 bg-error/10 rounded-lg px-3 py-2 border border-error/20"
                  >
                    <Zap size={14} className="shrink-0" /> {error}
                  </motion.p>
                )}

                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.6 }}
                >
                  <button
                    type="submit"
                    className="btn btn-success w-full rounded-xl font-semibold tracking-wide shadow-glow-sm hover:shadow-glow transition-shadow duration-300 border-0"
                    disabled={loading}
                  >
                    {loading ? (
                      <Loader2 size={18} className="animate-spin" />
                    ) : (
                      <>
                        <Zap size={16} /> Authenticate
                      </>
                    )}
                  </button>
                </motion.div>
              </form>

              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.7 }}
                className="text-center space-y-1"
              >
                <p className="text-[10px] text-base-content/30 font-mono tracking-wider">
                  AUTHORIZED PERSONNEL ONLY
                </p>
                <p className="text-[10px] text-base-content/20">
                  v2.0.0 · Lucy RATS Platform
                </p>
              </motion.div>
            </div>
          </div>
        </div>
      </motion.div>
    </div>
  )
}
