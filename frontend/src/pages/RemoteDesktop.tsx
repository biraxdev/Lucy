import { useEffect, useRef, useState, useCallback } from 'react'
import { useParams } from 'react-router-dom'
import { Monitor, MousePointer, Keyboard, Power, Maximize2, ZoomIn, ZoomOut, Clipboard } from 'lucide-react'
import { useWebSocket } from '../hooks/useWebSocket'

type StreamState = 'idle' | 'starting' | 'streaming' | 'stopped' | 'error'

const KEY_MAP: Record<string, string> = {
  Enter: 'enter', Tab: 'tab', Escape: 'esc', Backspace: 'backspace',
  Delete: 'delete', ArrowUp: 'up', ArrowDown: 'down', ArrowLeft: 'left', ArrowRight: 'right',
  Home: 'home', End: 'end', PageUp: 'page_up', PageDown: 'page_down',
  F1: 'f1', F2: 'f2', F3: 'f3', F4: 'f4', F5: 'f5', F6: 'f6',
  F7: 'f7', F8: 'f8', F9: 'f9', F10: 'f10', F11: 'f11', F12: 'f12',
  Control: 'ctrl', Alt: 'alt', Shift: 'shift', Meta: 'cmd',
}

export default function RemoteDesktop() {
  const { id: agentId } = useParams<{ id: string }>()
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const [state, setState] = useState<StreamState>('idle')
  const [fps, setFps] = useState(10)
  const [quality, setQuality] = useState(60)
  const [resolution, setResolution] = useState({ width: 1920, height: 1080 })
  const [frameCount, setFrameCount] = useState(0)
  const [controlEnabled, setControlEnabled] = useState(true)
  const [zoom, setZoom] = useState(1)
  const [statusMsg, setStatusMsg] = useState('')
  const pressedKeys = useRef<Set<string>>(new Set())
  const { subscribe, unsubscribe, on, send } = useWebSocket()

  const sendInput = useCallback((payload: object) => {
    if (!agentId || !controlEnabled) return
    send({ type: 'input_event', agent_id: agentId, payload })
  }, [agentId, controlEnabled])

  // Subscribe to screen frames
  useEffect(() => {
    if (!agentId) return
    const channel = `screen:${agentId}`
    subscribe(channel)

    const unsub = on('screen_frame', (msg: any) => {
      if (msg.agent_id !== agentId) return
      const { frame, width, height } = msg.data || msg.payload || msg
      if (width && height) setResolution({ width, height })
      if (!frame) return
      const canvas = canvasRef.current
      if (!canvas) return
      const ctx = canvas.getContext('2d')
      if (!ctx) return
      const img = new Image()
      img.onload = () => {
        canvas.width = img.width
        canvas.height = img.height
        ctx.drawImage(img, 0, 0)
        setFrameCount(c => c + 1)
      }
      img.src = `data:image/jpeg;base64,${frame}`
    })

    return () => { unsub(); unsubscribe(channel) }
  }, [agentId, subscribe, unsubscribe])

  // Draw single/first frame returned via task result
  useEffect(() => {
    if (!agentId) return
    const unsub = on('result', (msg: any) => {
      if (msg.agent_id !== agentId) return
      const p = msg.payload as any
      if (p?.module !== 'screen_stream') return
      const frame = p?.data?.frame || p?.data?.first_frame
      if (!frame) return
      const canvas = canvasRef.current
      if (!canvas) return
      const ctx = canvas.getContext('2d')
      if (!ctx) return
      const img = new Image()
      img.onload = () => {
        canvas.width = img.width
        canvas.height = img.height
        ctx.drawImage(img, 0, 0)
        setFrameCount(c => c + 1)
      }
      img.src = `data:image/jpeg;base64,${frame}`
    })
    return unsub
  }, [agentId, on])

  const startStream = () => {
    if (!agentId) return
    setState('starting')
    setStatusMsg('Démarrage du stream...')
    send({
      type: 'send_task',
      payload: {
        agent_id: agentId,
        module: 'screen_stream',
        action: 'start',
        params: { fps, quality },
      },
    })
    setTimeout(() => { setState('streaming'); setStatusMsg('') }, 1500)
  }

  const stopStream = () => {
    if (!agentId) return
    send({
      type: 'send_task',
      payload: { agent_id: agentId, module: 'screen_stream', action: 'stop', params: {} },
    })
    setState('stopped')
    setStatusMsg('Stream arrêté')
  }

  const singleFrame = () => {
    if (!agentId) return
    send({
      type: 'send_task',
      payload: { agent_id: agentId, module: 'screen_stream', action: 'frame', params: { quality } },
    })
  }

  // Mouse events on canvas
  const getCanvasCoords = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const rect = e.currentTarget.getBoundingClientRect()
    const scaleX = resolution.width / rect.width
    const scaleY = resolution.height / rect.height
    return {
      x: Math.round((e.clientX - rect.left) * scaleX),
      y: Math.round((e.clientY - rect.top) * scaleY),
    }
  }

  const handleMouseMove = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    if (state !== 'streaming') return
    const { x, y } = getCanvasCoords(e)
    sendInput({ action: 'mouse_move', x, y })
  }, [state, sendInput, resolution])

  const handleMouseClick = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    e.preventDefault()
    if (state !== 'streaming') return
    const { x, y } = getCanvasCoords(e)
    const btn = e.button === 2 ? 'right' : e.button === 1 ? 'middle' : 'left'
    sendInput({ action: 'mouse_click', x, y, button: btn })
  }, [state, sendInput, resolution])

  const handleWheel = useCallback((e: React.WheelEvent<HTMLCanvasElement>) => {
    e.preventDefault()
    if (state !== 'streaming') return
    const { x, y } = getCanvasCoords(e as any)
    sendInput({ action: 'mouse_scroll', x, y, dy: e.deltaY > 0 ? -3 : 3 })
  }, [state, sendInput, resolution])

  // Keyboard events
  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if (!controlEnabled || state !== 'streaming') return
    e.preventDefault()
    const key = KEY_MAP[e.key] || e.key.toLowerCase()
    if (pressedKeys.current.has(key)) return
    pressedKeys.current.add(key)
    const mods: string[] = []
    if (e.ctrlKey && key !== 'ctrl') mods.push('ctrl')
    if (e.altKey && key !== 'alt') mods.push('alt')
    if (e.shiftKey && key !== 'shift') mods.push('shift')
    if (mods.length > 0) {
      sendInput({ action: 'hotkey', keys: [...mods, key] })
    } else {
      sendInput({ action: 'key_press', key })
    }
  }, [controlEnabled, state, sendInput])

  const handleKeyUp = useCallback((e: KeyboardEvent) => {
    const key = KEY_MAP[e.key] || e.key.toLowerCase()
    pressedKeys.current.delete(key)
  }, [])

  useEffect(() => {
    if (state !== 'streaming') return
    window.addEventListener('keydown', handleKeyDown)
    window.addEventListener('keyup', handleKeyUp)
    return () => {
      window.removeEventListener('keydown', handleKeyDown)
      window.removeEventListener('keyup', handleKeyUp)
    }
  }, [state, handleKeyDown, handleKeyUp])

  const pasteToTarget = async () => {
    const text = await navigator.clipboard.readText()
    if (text) sendInput({ action: 'key_type', text })
  }

  return (
    <div className="flex flex-col h-full bg-gray-950">
      {/* Toolbar */}
      <div className="flex items-center gap-2 px-4 py-2 bg-gray-900 border-b border-gray-800 flex-wrap">
        <div className="flex items-center gap-2 mr-2">
          <Monitor size={18} className="text-green-400" />
          <span className="text-white font-semibold text-sm">Remote Desktop</span>
          <span className="text-gray-500 text-xs font-mono">{agentId?.slice(0, 8)}…</span>
        </div>

        <div className="h-5 w-px bg-gray-700" />

        {state !== 'streaming' ? (
          <button
            onClick={startStream}
            disabled={state === 'starting'}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-green-600 hover:bg-green-500 disabled:opacity-50 text-white rounded text-xs font-medium transition-colors"
          >
            <Power size={13} /> {state === 'starting' ? 'Démarrage…' : 'Démarrer stream'}
          </button>
        ) : (
          <button
            onClick={stopStream}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-red-700 hover:bg-red-600 text-white rounded text-xs font-medium transition-colors"
          >
            <Power size={13} /> Arrêter
          </button>
        )}

        <button
          onClick={singleFrame}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-gray-700 hover:bg-gray-600 text-white rounded text-xs transition-colors"
        >
          <Maximize2 size={13} /> Capture
        </button>

        <div className="h-5 w-px bg-gray-700" />

        <label className="flex items-center gap-1.5 text-gray-400 text-xs">
          <MousePointer size={13} />
          <input
            type="checkbox"
            checked={controlEnabled}
            onChange={e => setControlEnabled(e.target.checked)}
            className="w-3 h-3"
          />
          Contrôle
        </label>

        <div className="h-5 w-px bg-gray-700" />

        <label className="flex items-center gap-1.5 text-gray-400 text-xs">
          FPS
          <select
            value={fps}
            onChange={e => setFps(Number(e.target.value))}
            className="bg-gray-800 text-white text-xs rounded px-1 py-0.5 border border-gray-700"
          >
            {[2, 5, 10, 15, 20, 30].map(f => <option key={f}>{f}</option>)}
          </select>
        </label>

        <label className="flex items-center gap-1.5 text-gray-400 text-xs">
          Qualité
          <select
            value={quality}
            onChange={e => setQuality(Number(e.target.value))}
            className="bg-gray-800 text-white text-xs rounded px-1 py-0.5 border border-gray-700"
          >
            <option value={30}>Basse (30)</option>
            <option value={60}>Moyenne (60)</option>
            <option value={80}>Haute (80)</option>
            <option value={95}>Max (95)</option>
          </select>
        </label>

        <div className="h-5 w-px bg-gray-700" />

        <button onClick={() => setZoom(z => Math.min(z + 0.1, 3))} className="text-gray-400 hover:text-white p-1 rounded">
          <ZoomIn size={14} />
        </button>
        <span className="text-gray-500 text-xs w-10 text-center">{Math.round(zoom * 100)}%</span>
        <button onClick={() => setZoom(z => Math.max(z - 0.1, 0.3))} className="text-gray-400 hover:text-white p-1 rounded">
          <ZoomOut size={14} />
        </button>

        <button onClick={pasteToTarget} className="flex items-center gap-1 text-gray-400 hover:text-white text-xs px-2 py-1 rounded bg-gray-800 ml-auto">
          <Clipboard size={13} /> Coller sur cible
        </button>

        {/* Status / frame counter */}
        <div className="ml-2 text-xs text-gray-500">
          {state === 'streaming' && <span className="text-green-400">● {frameCount} frames</span>}
          {statusMsg && <span className="text-yellow-400">{statusMsg}</span>}
          {state === 'idle' && <span>En attente</span>}
        </div>
      </div>

      {/* Canvas area */}
      <div
        ref={containerRef}
        className="flex-1 overflow-auto bg-black flex items-center justify-center"
        style={{ cursor: controlEnabled && state === 'streaming' ? 'none' : 'default' }}
      >
        {state === 'idle' || state === 'stopped' ? (
          <div className="text-center text-gray-600">
            <Monitor size={64} className="mx-auto mb-4 opacity-30" />
            <p className="text-lg">Aucun stream actif</p>
            <p className="text-sm mt-1">Clique sur <strong>"Démarrer stream"</strong> ou <strong>"Capture"</strong> pour une frame unique</p>
          </div>
        ) : state === 'starting' ? (
          <div className="text-center text-gray-500">
            <div className="animate-pulse text-green-400 text-4xl mb-4">⬤</div>
            <p>Connexion à l'agent…</p>
          </div>
        ) : (
          <canvas
            ref={canvasRef}
            style={{ transform: `scale(${zoom})`, transformOrigin: 'top left', imageRendering: 'pixelated', cursor: controlEnabled ? 'crosshair' : 'default' }}
            onMouseMove={handleMouseMove}
            onClick={handleMouseClick}
            onContextMenu={handleMouseClick}
            onWheel={handleWheel}
            className="block"
            tabIndex={0}
          />
        )}
      </div>

      {/* Bottom info bar */}
      <div className="flex items-center gap-4 px-4 py-1.5 bg-gray-900 border-t border-gray-800 text-xs text-gray-500">
        <span>Résolution cible: <span className="text-gray-300">{resolution.width}×{resolution.height}</span></span>
        <span>Zoom: <span className="text-gray-300">{Math.round(zoom * 100)}%</span></span>
        <span className={controlEnabled ? 'text-green-400' : 'text-gray-500'}>
          <MousePointer size={11} className="inline mr-1" />
          {controlEnabled ? 'Contrôle activé' : 'Contrôle désactivé'}
        </span>
        <span className={controlEnabled && state === 'streaming' ? 'text-green-400' : 'text-gray-500'}>
          <Keyboard size={11} className="inline mr-1" />
          {controlEnabled && state === 'streaming' ? 'Clavier capturé' : ''}
        </span>
      </div>
    </div>
  )
}
