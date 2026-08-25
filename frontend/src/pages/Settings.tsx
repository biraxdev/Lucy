import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useAuthStore } from '../stores/authStore'
import { useUIStore } from '../stores/uiStore'
import { changePassword, changeUsername, rotateApiKey } from '../api/auth'
import api from '../api/client'
import { Shield, Moon, Sun, KeyRound, Lock, Server, Cpu, HardDrive, User } from 'lucide-react'
import ScreenshotSchedulerCard from '../components/ScreenshotSchedulerCard'

export default function Settings() {
  const { user } = useAuthStore()
  const { theme, setTheme } = useUIStore()
  const [oldPwd, setOldPwd] = useState('')
  const [newPwd, setNewPwd] = useState('')
  const [pwdMsg, setPwdMsg] = useState<{ ok: boolean; text: string } | null>(null)
  const [apiKey, setApiKey] = useState<string | null>(null)
  const [pwdForUser, setPwdForUser] = useState('')
  const [newUser, setNewUser] = useState('')
  const [userMsg, setUserMsg] = useState<{ ok: boolean; text: string } | null>(null)

  const handlePwdChange = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      await changePassword(oldPwd, newPwd)
      setPwdMsg({ ok: true, text: 'Password changed successfully.' })
      setOldPwd(''); setNewPwd('')
    } catch {
      setPwdMsg({ ok: false, text: 'Failed to change password.' })
    }
  }

  const handleUserChange = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      await changeUsername(pwdForUser, newUser)
      setUserMsg({ ok: true, text: 'Username changed successfully. Log in again with the new username.' })
      setPwdForUser(''); setNewUser('')
    } catch {
      setUserMsg({ ok: false, text: 'Failed to change username.' })
    }
  }

  const handleRotate = async () => {
    try {
      const res = await rotateApiKey()
      setApiKey((res.data as any).api_key)
    } catch {
      setApiKey('Error rotating key')
    }
  }

  const { data: health } = useQuery({
    queryKey: ['monitor-health'],
    queryFn: () => api.get<any>('/monitor').then(r => r.data).catch(() => null),
    refetchInterval: 10000,
  })

  return (
    <div className="page-container max-w-2xl space-y-6">
      <h1 className="text-2xl font-bold flex items-center gap-2"><Shield size={22} /> Settings</h1>

      {health && (
        <div className="card bg-base-200 p-5 space-y-3">
          <h2 className="font-semibold flex items-center gap-2"><Server size={16} /> Server Status</h2>
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div>
              <p className="text-xs text-base-content/50 flex items-center gap-1"><Cpu size={11}/> CPU</p>
              <div className="flex items-center gap-2 mt-1">
                <progress className="progress progress-success w-24 h-2" value={health.cpu_percent ?? 0} max={100} />
                <span className="font-mono text-xs">{health.cpu_percent?.toFixed(1)}%</span>
              </div>
            </div>
            <div>
              <p className="text-xs text-base-content/50 flex items-center gap-1"><HardDrive size={11}/> RAM</p>
              <div className="flex items-center gap-2 mt-1">
                <progress className="progress progress-info w-24 h-2" value={health.ram_percent ?? 0} max={100} />
                <span className="font-mono text-xs">{health.ram_percent?.toFixed(1)}%</span>
              </div>
            </div>
            <div>
              <p className="text-xs text-base-content/50">Active WS connections</p>
              <p className="font-mono">{health.ws_connections ?? '—'}</p>
            </div>
            <div>
              <p className="text-xs text-base-content/50">DB size</p>
              <p className="font-mono">{health.db_size_mb ? `${health.db_size_mb} MB` : '—'}</p>
            </div>
            <div>
              <p className="text-xs text-base-content/50">Uptime</p>
              <p className="font-mono text-xs">{health.uptime ?? '—'}</p>
            </div>
            <div>
              <p className="text-xs text-base-content/50">Version</p>
              <p className="font-mono text-xs">{health.version ?? '—'}</p>
            </div>
          </div>
        </div>
      )}

      <div className="card bg-base-200 p-5 space-y-3">
        <h2 className="font-semibold">Profile</h2>
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div><p className="text-base-content/50 text-xs">Username</p><p className="font-mono">{user?.username}</p></div>
          <div><p className="text-base-content/50 text-xs">Role</p><p className="badge badge-sm badge-outline">{user?.role}</p></div>
          <div><p className="text-base-content/50 text-xs">Email</p><p>{user?.email || '—'}</p></div>
        </div>
      </div>

      <div className="card bg-base-200 p-5 space-y-3">
        <h2 className="font-semibold flex items-center gap-2"><User size={16} /> Change Username</h2>
        <form onSubmit={handleUserChange} className="flex flex-col gap-3">
          <input type="password" className="input input-bordered input-sm" placeholder="Current password"
            value={pwdForUser} onChange={(e) => setPwdForUser(e.target.value)} required />
          <input type="text" className="input input-bordered input-sm" placeholder="New username"
            value={newUser} onChange={(e) => setNewUser(e.target.value)} required />
          {userMsg && <p className={`text-xs ${userMsg.ok ? 'text-success' : 'text-error'}`}>{userMsg.text}</p>}
          <button type="submit" className="btn btn-sm btn-outline w-fit">Change Username</button>
        </form>
      </div>

      <div className="card bg-base-200 p-5 space-y-3">
        <h2 className="font-semibold flex items-center gap-2"><Moon size={16} /> Appearance</h2>
        <div className="flex gap-2">
          {(['dark', 'light'] as const).map((t) => (
            <button
              key={t}
              className={`btn btn-sm gap-1 ${theme === t ? 'btn-success' : 'btn-outline'}`}
              onClick={() => setTheme(t)}
            >
              {t === 'dark' ? <Moon size={12} /> : <Sun size={12} />}
              {t}
            </button>
          ))}
        </div>
      </div>

      <div className="card bg-base-200 p-5 space-y-3">
        <h2 className="font-semibold flex items-center gap-2"><Lock size={16} /> Change Password</h2>
        <form onSubmit={handlePwdChange} className="flex flex-col gap-3">
          <input type="password" className="input input-bordered input-sm" placeholder="Current password"
            value={oldPwd} onChange={(e) => setOldPwd(e.target.value)} required />
          <input type="password" className="input input-bordered input-sm" placeholder="New password"
            value={newPwd} onChange={(e) => setNewPwd(e.target.value)} required />
          {pwdMsg && <p className={`text-xs ${pwdMsg.ok ? 'text-success' : 'text-error'}`}>{pwdMsg.text}</p>}
          <button type="submit" className="btn btn-sm btn-outline w-fit">Change Password</button>
        </form>
      </div>

      <div className="card bg-base-200 p-5 space-y-3">
        <h2 className="font-semibold flex items-center gap-2"><KeyRound size={16} /> API Key</h2>
        {apiKey && (
          <div className="alert alert-success text-xs font-mono break-all">{apiKey}</div>
        )}
        <button className="btn btn-sm btn-warning gap-1" onClick={handleRotate}>
          <KeyRound size={12} /> Rotate API Key
        </button>
        <p className="text-xs text-base-content/40">Previous key will be invalidated immediately.</p>
      </div>

      <ScreenshotSchedulerCard />
    </div>
  )
}
