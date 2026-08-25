import { useEffect, useRef, useState, useCallback } from 'react'
import { useQuery } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import { Send, Sparkles, Globe, Users, Hash, Search, ChevronRight, Waves, BookOpen, Zap } from 'lucide-react'
import { useChatStore } from '../stores/chatStore'
import { useWebSocket } from '../hooks/useWebSocket'
import {
  sendChatCommand, getChatHistory, getChatChannels,
  getShannonStatus, setShannonMode, narrateRecent,
  streamShannonResponse, streamShannonLogs,
} from '../api/chat'
import ChatMessageComponent from '../components/ChatMessage'
import { PageTransition } from '../components/ui/PageTransition'
import type { ChatMessage } from '../types/chat'

const GLOBAL_CHANNEL = 'global'
type ShannonMode = 'narrative' | 'hybrid' | 'llm'

export default function Chat() {
  const { messages, pending, draft, setDraft, appendMessage, setMessages, updateMessage, markAllRead, setPending } = useChatStore()
  const [activeChannel, setActiveChannel] = useState<string>(GLOBAL_CHANNEL)
  const [channelSearch, setChannelSearch] = useState('')
  const [shannonMode, setShannonModeState] = useState<ShannonMode>('hybrid')
  const [shannonEnabled, setShannonEnabled] = useState(true)
  const [streamingText, setStreamingText] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const activeChannelRef = useRef<string>(GLOBAL_CHANNEL)
  const { on } = useWebSocket()

  // Load ShannonAi status
  const { data: shannonStatus } = useQuery({
    queryKey: ['shannon-status'],
    queryFn: getShannonStatus,
    refetchInterval: 30_000,
  })

  useEffect(() => {
    if (shannonStatus?.mode) setShannonModeState(shannonStatus.mode as ShannonMode)
  }, [shannonStatus?.mode])

  const handleShannonModeChange = async (mode: ShannonMode) => {
    setShannonModeState(mode)
    try { await setShannonMode(mode) } catch { /* ignore */ }
  }

  // Load available channels (global + groups).
  const { data: channels = [], refetch: refetchChannels } = useQuery({
    queryKey: ['chat-channels'],
    queryFn: getChatChannels,
    refetchInterval: 30_000,
  })

  // Load history when channel changes.
  useEffect(() => {
    let mounted = true
    activeChannelRef.current = activeChannel
    setMessages([])
    getChatHistory({ channel: activeChannel, limit: 100 })
      .then((history) => {
        if (mounted && activeChannel === activeChannelRef.current) {
          setMessages(history.reverse())
          markAllRead()
        }
      })
      .catch(() => {})
    return () => { mounted = false }
  }, [activeChannel, setMessages, markAllRead])

  // Subscribe to live chat events and route by channel.
  useEffect(() => {
    const cleanup = on('chat', (msg: any) => {
      if (!msg?.payload) return
      const payload = msg.payload as ChatMessage
      const msgChannels: string[] = payload.channels || [GLOBAL_CHANNEL]
      // Only append if the message belongs to the active channel.
      if (!msgChannels.includes(activeChannel)) return
      appendMessage({
        ...payload,
        id: payload.id || crypto.randomUUID(),
        created_at: payload.created_at || new Date().toISOString(),
      })
    })
    return cleanup
  }, [on, appendMessage, activeChannel])

  // Auto-scroll to bottom when messages change.
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = async () => {
    const text = draft.trim()
    if (!text || pending) return

    setPending(true)
    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: text,
      channel: activeChannel,
      created_at: new Date().toISOString(),
    }
    appendMessage(userMessage)
    setDraft('')

    // ShannonAi streaming mode — stream the response word-by-word.
    if (shannonEnabled) {
      const assistantId = crypto.randomUUID()
      setStreamingText('')
      appendMessage({
        id: assistantId,
        role: 'assistant',
        content: '',
        channel: activeChannel,
        source_event_type: 'shannon_stream',
        metadata: { shannon: true, mode: shannonMode },
        created_at: new Date().toISOString(),
      })
      try {
        // Special command: "narrate logs" triggers log-to-dialogue streaming.
        const lower = text.toLowerCase()
        if (lower.startsWith('narrate logs') || lower.startsWith('narrate recent')) {
          const full = await streamShannonLogs({ limit: 30 }, (chunk) => {
            setStreamingText((prev) => prev + chunk)
          })
          // Replace the assistant message content with the full narrative.
          updateMessage(assistantId, (m) => ({ ...m, content: full }))
        } else {
          const full = await streamShannonResponse(text, { channel: activeChannel }, (chunk) => {
            setStreamingText((prev) => prev + chunk)
          })
          updateMessage(assistantId, (m) => ({ ...m, content: full }))
        }
      } catch (err: any) {
        updateMessage(assistantId, (m) => ({
          ...m,
          content: `I'm sorry, I couldn't stream that: ${err?.message || 'unknown error'}`,
          source_event_type: 'error',
        }))
      } finally {
        setStreamingText('')
        setPending(false)
        inputRef.current?.focus()
      }
      return
    }

    // Standard (non-streaming) command path.
    try {
      const response = await sendChatCommand(text, { channel: activeChannel })
      appendMessage({
        id: crypto.randomUUID(),
        role: 'assistant',
        content: response.message,
        channel: activeChannel,
        raw_payload: { ...response },
        source_event_type: 'command_response',
        metadata: { intent: response.intent, status: response.status },
        created_at: new Date().toISOString(),
      })
    } catch (err: any) {
      appendMessage({
        id: crypto.randomUUID(),
        role: 'assistant',
        content: `I'm sorry, I couldn't send that: ${err?.message || 'unknown error'}`,
        channel: activeChannel,
        source_event_type: 'error',
        metadata: { mood: 'worried' },
        created_at: new Date().toISOString(),
      })
    } finally {
      setPending(false)
      inputRef.current?.focus()
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const activeChannelInfo = channels.find(c => c.id === activeChannel)
  const filteredChannels = channels.filter(c =>
    c.label.toLowerCase().includes(channelSearch.toLowerCase())
  )

  const quickCommands = shannonEnabled
    ? [
        'narrate recent',
        'narrate logs',
        'summarize',
        'check on Agent 01',
      ]
    : [
        'check on Agent 01',
        'run recon on group Alpha',
        'show credentials from Agent 01',
        'summarize',
      ]

  return (
    <PageTransition>
      <div className="flex h-full">
        {/* Channel sidebar */}
        <aside className="w-64 shrink-0 border-r border-base-300 bg-base-200/50 flex flex-col">
          <div className="p-4 border-b border-base-300">
            <h2 className="font-bold text-sm flex items-center gap-2 mb-3">
              <Sparkles className="text-success" size={16} />
              Conversations
            </h2>
            <div className="relative">
              <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-base-content/40" />
              <input
                type="text"
                value={channelSearch}
                onChange={(e) => setChannelSearch(e.target.value)}
                placeholder="Search channels…"
                className="input input-bordered input-xs w-full pl-7"
              />
            </div>
          </div>

          <div className="flex-1 overflow-y-auto scrollbar-thin p-2 space-y-1">
            {filteredChannels.map((ch) => {
              const isActive = ch.id === activeChannel
              const Icon = ch.type === 'global' ? Globe : Users
              return (
                <motion.button
                  key={ch.id}
                  whileHover={{ x: 2 }}
                  onClick={() => setActiveChannel(ch.id)}
                  className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-left transition-colors ${
                    isActive
                      ? 'bg-success/10 border border-success/20'
                      : 'border border-transparent hover:bg-base-300'
                  }`}
                >
                  <div
                    className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0"
                    style={{ backgroundColor: `${ch.color}15` }}
                  >
                    <Icon size={15} style={{ color: ch.color }} />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className={`text-sm font-semibold truncate ${isActive ? 'text-success' : ''}`}>
                      {ch.label}
                    </p>
                    <p className="text-[10px] text-base-content/40 truncate">
                      {ch.type === 'global' ? 'All agents feed' : `${ch.member_count} member${ch.member_count !== 1 ? 's' : ''}`}
                    </p>
                  </div>
                  {isActive && <ChevronRight size={14} className="text-success shrink-0" />}
                </motion.button>
              )
            })}
            {filteredChannels.length === 0 && (
              <p className="text-center text-xs text-base-content/30 py-6">No channels found.</p>
            )}
          </div>

          {/* ShannonAi panel */}
          <div className="border-t border-base-300 p-3 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-bold uppercase tracking-wider text-base-content/50 flex items-center gap-1">
                <Waves size={11} className="text-info" /> ShannonAi
              </span>
              <label className="toggle toggle-xs">
                <input
                  type="checkbox"
                  checked={shannonEnabled}
                  onChange={(e) => setShannonEnabled(e.target.checked)}
                />
                <span className="toggle-slider" />
              </label>
            </div>
            {shannonEnabled && (
              <div className="flex gap-1">
                {(['narrative', 'hybrid', 'llm'] as ShannonMode[]).map((m) => (
                  <button
                    key={m}
                    onClick={() => handleShannonModeChange(m)}
                    className={`btn btn-xs flex-1 gap-0.5 ${shannonMode === m ? 'btn-info' : 'btn-ghost'}`}
                    title={
                      m === 'narrative' ? 'Local narrative engine only'
                      : m === 'hybrid' ? 'Narrative + LLM polish'
                      : 'Full LLM generation (requires Ollama)'
                    }
                  >
                    {m === 'narrative' ? <BookOpen size={10} /> : m === 'hybrid' ? <Waves size={10} /> : <Zap size={10} />}
                    {m.slice(0, 4)}
                  </button>
                ))}
              </div>
            )}
            {shannonStatus && (
              <p className="text-[9px] text-base-content/40">
                {shannonStatus.event_count} events · {shannonStatus.agents_tracked} agents
                {shannonStatus.llm_available && ' · LLM ✓'}
              </p>
            )}
          </div>
        </aside>

        {/* Chat area */}
        <div className="flex flex-col flex-1 min-w-0">
          {/* Channel header */}
          <div className="px-6 py-3 border-b border-base-300 bg-base-200/30 flex items-center justify-between">
            <div className="flex items-center gap-3 min-w-0">
              <div
                className="w-9 h-9 rounded-xl flex items-center justify-center shrink-0"
                style={{ backgroundColor: `${activeChannelInfo?.color || '#22c55e'}15` }}
              >
                {activeChannelInfo?.type === 'global' ? (
                  <Globe size={18} style={{ color: activeChannelInfo?.color || '#22c55e' }} />
                ) : (
                  <Users size={18} style={{ color: activeChannelInfo?.color || '#22c55e' }} />
                )}
              </div>
              <div className="min-w-0">
                <h1 className="font-bold text-base truncate">{activeChannelInfo?.label || 'Global Feed'}</h1>
                <p className="text-[11px] text-base-content/50 truncate">
                  {activeChannelInfo?.type === 'global'
                    ? 'Live feed from all agents — heartbeats, results, alerts'
                    : activeChannelInfo?.description || `${activeChannelInfo?.member_count || 0} agents`}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-1.5 text-[10px] text-success font-semibold">
              <span className="w-2 h-2 rounded-full bg-success animate-pulse" />
              LIVE
            </div>
            {shannonEnabled && (
              <div className="flex items-center gap-1 text-[10px] text-info font-semibold ml-2">
                <Waves size={11} className="animate-pulse" />
                SHANNON
              </div>
            )}
          </div>

          {/* Messages feed */}
          <div className="flex-1 overflow-y-auto scrollbar-thin px-4 py-4 space-y-1">
            <AnimatePresence initial={false}>
              {messages.length === 0 && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="text-center text-base-content/40 py-16 space-y-2"
                >
                  <Hash size={32} className="mx-auto opacity-40" />
                  <p className="text-sm">No messages in this channel yet.</p>
                  <p className="text-xs">Agent events will appear here in real-time.</p>
                </motion.div>
              )}
              {messages.map((m) => (
                <motion.div
                  key={m.id}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.2 }}
                >
                  <ChatMessageComponent
                    message={m}
                    streamingText={m.source_event_type === 'shannon_stream' && pending ? streamingText : undefined}
                  />
                </motion.div>
              ))}
            </AnimatePresence>
            {streamingText && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="px-3 py-1 text-[10px] text-info/60 flex items-center gap-1"
              >
                <Waves size={10} className="animate-pulse" /> ShannonAi is narrating…
              </motion.div>
            )}
            <div ref={bottomRef} />
          </div>

          {/* Quick commands */}
          <div className="px-4 py-2 border-t border-base-300/50 flex flex-wrap gap-1.5">
            {quickCommands.map((cmd) => (
              <button
                key={cmd}
                type="button"
                onClick={() => {
                  setDraft(cmd)
                  inputRef.current?.focus()
                }}
                className="badge badge-outline cursor-pointer hover:badge-success transition-colors text-[11px]"
              >
                {cmd}
              </button>
            ))}
          </div>

          {/* Input bar */}
          <div className="px-4 py-3 border-t border-base-300 bg-base-200/30">
            <div className="flex gap-2">
              <input
                ref={inputRef}
                type="text"
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={`Message ${activeChannelInfo?.label || 'global'}…`}
                className="input input-bordered flex-1 input-sm"
                disabled={pending}
              />
              <button
                type="button"
                onClick={handleSend}
                disabled={pending || !draft.trim()}
                className="btn btn-success btn-sm gap-1"
              >
                {pending ? <span className="loading loading-spinner loading-xs" /> : <Send size={16} />}
                Send
              </button>
            </div>
          </div>
        </div>
      </div>
    </PageTransition>
  )
}
