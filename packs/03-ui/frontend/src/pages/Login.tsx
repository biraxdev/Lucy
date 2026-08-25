import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ShieldAlert, Loader2 } from 'lucide-react'
import { login, me } from '../api/auth'
import { useAuthStore } from '../stores/authStore'

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
    <div className="min-h-screen flex items-center justify-center bg-base-100">
      <div className="card w-full max-w-sm bg-base-200 shadow-xl border border-base-300">
        <div className="card-body gap-6">
          <div className="flex flex-col items-center gap-2">
            <ShieldAlert size={40} className="text-success" />
            <h1 className="text-2xl font-bold">Lucy C2</h1>
            <p className="text-xs text-base-content/50">Remote Agent Testing System</p>
          </div>

          <form onSubmit={handleSubmit} className="flex flex-col gap-3">
            <label className="form-control">
              <span className="label-text mb-1">Username</span>
              <input
                className="input input-bordered w-full"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoFocus
                required
              />
            </label>

            <label className="form-control">
              <span className="label-text mb-1">Password</span>
              <input
                type="password"
                className="input input-bordered w-full"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </label>

            {error && <p className="text-error text-sm">{error}</p>}

            <button type="submit" className="btn btn-success w-full mt-2" disabled={loading}>
              {loading ? <Loader2 size={16} className="animate-spin" /> : 'Sign In'}
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}
