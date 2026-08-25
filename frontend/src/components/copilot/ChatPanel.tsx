import { useEffect, useRef, useState, useCallback } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Send, Loader2, Brain, RotateCcw, AlertCircle,
  Server, Zap, Code, Globe, Activity, KeyRound, Camera, Wifi, ShieldAlert,
} from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import ReactMarkdown from 'react-markdown'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism'
import { useCopilotStore } from '../../stores/copilotStore'
import { streamChat, getCopilotContext, type CopilotContext } from '../../api/copilot'
import { getChatHistory, clearChat } from '../../api/ai_chat'

interface Msg {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  streaming?: boolean
  timestamp: Date
}

const quickActions = [
  { icon: Zap, label: 'Recon express', text: 'Fais un recon express de l\'agent FBOX: système, écran, réseau, identité' },
  { icon: KeyRound, label: 'Récolte credentials', text: 'Récupère tous les credentials: passwords navigateurs, WiFi, credential manager, SSH keys' },
  { icon: Camera, label: 'Screenshot', text: 'Prends un screenshot de l\'agent FBOX maintenant' },
  { icon: Wifi, label: 'Audit WiFi', text: 'Fais un audit WiFi complet: statut, scan, profils, credentials' },
  { icon: ShieldAlert, label: 'Check EDR/AV', text: 'Vérifie si il y a un antivirus ou EDR sur l\'agent FBOX' },
  { icon: Brain, label: 'Analyse situation', text: 'Analyse la situation actuelle de Lucy et suggère les prochaines étapes' },
]

export function ChatPanel() {
  const { sessionId, contextPage, prefillMessage, setPrefill } = useCopilotStore()
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState<Msg[]>([])
  const [streaming, setStreaming] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  const queryClient = useQueryClient()

  const { data: context } = useQuery<CopilotContext>({
    queryKey: ['copilot-context'],
    queryFn: getCopilotContext,
    refetchInterval: 15000,
  })

  // Load history on mount
  useEffect(() => {
    getChatHistory(sessionId).then((h) => {
      if (h.messages?.length) {
        setMessages(h.messages.map((m: any) => ({
          id: `${m.timestamp}-${Math.random()}`,
          role: m.role,
          content: m.content,
          timestamp: new Date(m.timestamp),
        })))
      }
    }).catch(() => {})
  }, [sessionId])

  // Handle prefill from other components
  useEffect(() => {
    if (prefillMessage) {
      setInput(prefillMessage)
      setPrefill(null)
    }
  }, [prefillMessage, setPrefill])

  const scrollToBottom = useCallback(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [])

  useEffect(() => {
    scrollToBottom()
  }, [messages, scrollToBottom])

  const handleSend = async () => {
    const msg = input.trim()
    if (!msg || streaming) return

    const userMsg: Msg = {
      id: crypto.randomUUID(),
      role: 'user',
      content: msg,
      timestamp: new Date(),
    }
    const assistantId = crypto.randomUUID()
    const assistantMsg: Msg = {
      id: assistantId,
      role: 'assistant',
      content: '',
      streaming: true,
      timestamp: new Date(),
    }

    setMessages((prev) => [...prev, userMsg, assistantMsg])
    setInput('')
    setStreaming(true)

    try {
      let fullResponse = ''
      for await (const event of streamChat(msg, sessionId, contextPage)) {
        if (event.type === 'token' && event.content) {
          fullResponse += event.content
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId ? { ...m, content: fullResponse } : m
            )
          )
        } else if (event.type === 'done') {
          if (event.message && fullResponse.length < event.message.length) {
            fullResponse = event.message
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId ? { ...m, content: fullResponse } : m
              )
            )
          }
        } else if (event.type === 'error') {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? { ...m, content: `⚠️ Erreur: ${event.message}`, streaming: false, role: 'system' }
                : m
            )
          )
        }
      }
      setMessages((prev) =>
        prev.map((m) => (m.id === assistantId ? { ...m, streaming: false } : m))
      )
    } catch (err: any) {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId
            ? { ...m, content: `⚠️ Erreur de connexion: ${err.message}`, streaming: false, role: 'system' }
            : m
        )
      )
    } finally {
      setStreaming(false)
      queryClient.invalidateQueries({ queryKey: ['copilot-context'] })
    }
  }

  const handleClear = async () => {
    await clearChat(sessionId)
    setMessages([])
  }

  const renderContent = (msg: Msg) => {
    if (msg.role === 'system') {
      return (
        <div className="flex items-center gap-2 text-xs text-error">
          <AlertCircle size={14} /> {msg.content}
        </div>
      )
    }
    return (
      <ReactMarkdown
        className="prose prose-sm prose-invert max-w-none"
        components={{
          code({ node, inline, className, children, ...props }: any) {
            const match = /language-(\w+)/.exec(className || '')
            const codeStr = String(children).replace(/\n$/, '')
            return !inline && match ? (
              <div className="relative my-1">
                <button
                  className="absolute top-1 right-1 btn btn-xs btn-ghost btn-square opacity-60 hover:opacity-100"
                  onClick={() => navigator.clipboard.writeText(codeStr)}
                >
                  <span className="text-[10px]">Copy</span>
                </button>
                <SyntaxHighlighter style={vscDarkPlus} language={match[1]} PreTag="div" {...props}>
                  {codeStr}
                </SyntaxHighlighter>
              </div>
            ) : (
              <code className="bg-base-300 px-1 py-0.5 rounded text-xs font-mono" {...props}>{children}</code>
            )
          },
        }}
      >
        {msg.content || (msg.streaming ? '...' : '')}
      </ReactMarkdown>
    )
  }

  return (
    <div className="flex flex-col h-full min-h-0">
      {/* Context bar */}
      {context && (
        <div className="shrink-0 px-3 py-1.5 border-b border-base-300 bg-base-200/50 flex items-center gap-3 text-[10px] text-base-content/50">
          <span className="flex items-center gap-1">
            <Server size={10} className="text-success" />
            {context.stats.agents_online || 0}/{context.stats.agents || 0} agents
          </span>
          <span className="flex items-center gap-1">
            <Activity size={10} className="text-info" />
            {context.stats.tasks || 0} tasks
          </span>
          <span className="flex items-center gap-1">
            <Code size={10} className="text-warning" />
            {context.stats.modules || 0} modules
          </span>
          {contextPage && (
            <span className="ml-auto badge badge-xs badge-ghost">📍 {contextPage}</span>
          )}
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-3 space-y-3 min-h-0 scrollbar-thin">
        {messages.length === 0 && (
          <div className="text-center text-base-content/30 py-6 space-y-4">
            <Brain size={40} className="mx-auto opacity-30" />
            <div className="space-y-1">
              <p className="text-sm font-medium">Lucy AI Copilot</p>
              <p className="text-xs max-w-xs mx-auto">
                Je contrôle toute la plateforme. Parle-moi en langage naturel.
              </p>
            </div>
            <div className="grid grid-cols-1 gap-1.5 max-w-xs mx-auto mt-3">
              {quickActions.map((qa, i) => (
                <button
                  key={i}
                  className="btn btn-xs btn-outline gap-2 justify-start normal-case text-xs"
                  onClick={() => setInput(qa.text)}
                >
                  <qa.icon size={12} /> {qa.label}
                </button>
              ))}
            </div>
          </div>
        )}

        <AnimatePresence>
          {messages.map((msg) => (
            <motion.div
              key={msg.id}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div className={`max-w-[88%] rounded-xl p-2.5 space-y-1 ${
                msg.role === 'user'
                  ? 'bg-success/15 text-success-content'
                  : msg.role === 'system'
                    ? 'bg-error/10 border border-error/20'
                    : 'bg-base-300 text-base-content'
              }`}>
                <div className="flex items-center gap-1.5 text-[9px] opacity-50 uppercase font-semibold">
                  {msg.role === 'user' ? 'You' : msg.role === 'system' ? 'Error' : (
                    <><Brain size={9} className="text-success" /> Copilot</>
                  )}
                  {msg.streaming && <Loader2 size={9} className="animate-spin" />}
                </div>
                {renderContent(msg)}
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="shrink-0 p-2.5 border-t border-base-300">
        <div className="flex gap-1.5 items-end">
          <textarea
            className="textarea textarea-bordered flex-1 min-h-[2.5rem] max-h-[6rem] text-sm resize-y bg-base-200"
            placeholder="Demande quelque chose à Lucy..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                handleSend()
              }
            }}
            disabled={streaming}
            rows={1}
          />
          <button
            className="btn btn-sm btn-success gap-1"
            onClick={handleSend}
            disabled={streaming || !input.trim()}
          >
            {streaming ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
          </button>
          <button
            className="btn btn-sm btn-ghost btn-square"
            onClick={handleClear}
            title="Effacer la conversation"
          >
            <RotateCcw size={14} />
          </button>
        </div>
        <div className="flex gap-1 mt-1.5 flex-wrap">
          {['recon express FBOX', 'récupère les credentials', 'audit WiFi', 'check EDR', 'screenshot maintenant'].map((cmd) => (
            <button
              key={cmd}
              className="badge badge-xs badge-ghost cursor-pointer hover:badge-success text-[10px]"
              onClick={() => setInput(cmd)}
            >
              {cmd}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
