import { useEffect, useRef, useState, useCallback } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Brain, Send, Loader2, Terminal, Code, Wand2, AlertTriangle,
  Check, X, Play, Copy, ChevronRight, RotateCcw, Sparkles,
  Zap, MessageSquare, FileCode, Box, Activity, HelpCircle
} from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import ReactMarkdown from 'react-markdown'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism'
import { Card } from '../components/ui/Card'
import { PageTransition } from '../components/ui/PageTransition'
import {
  sendChatMessage, getChatHistory, clearChat, getChatStatus,
  type ChatResponse, type ChatHistoryResponse
} from '../api/ai_chat'

interface DisplayMessage {
  id: string
  role: 'user' | 'assistant' | 'system' | 'thinking' | 'plan' | 'execution'
  content: string
  type?: string
  questions?: string[]
  metadata?: Record<string, unknown>
  timestamp: Date
}

export default function AIChat() {
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState<DisplayMessage[]>([])
  const [sessionId, setSessionId] = useState('default')
  const [isThinking, setIsThinking] = useState(false)
  const [pendingQuestions, setPendingQuestions] = useState<string[] | null>(null)
  const [forceExec, setForceExec] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  const queryClient = useQueryClient()

  const { data: history, isLoading: historyLoading } = useQuery({
    queryKey: ['ai-chat-history', sessionId],
    queryFn: () => getChatHistory(sessionId),
    refetchInterval: 5000,
  })

  const { data: status } = useQuery({
    queryKey: ['ai-chat-status', sessionId],
    queryFn: () => getChatStatus(sessionId),
    refetchInterval: 3000,
  })

  const chatMut = useMutation({
    mutationFn: sendChatMessage,
    onMutate: () => {
      setIsThinking(true)
      setPendingQuestions(null)
    },
    onSuccess: (res) => {
      setIsThinking(false)
      if (res.type === 'clarification' && res.questions) {
        setPendingQuestions(res.questions)
        addMsg('assistant', res.message, 'clarification', res.questions)
      } else if (res.type === 'execution_report') {
        addMsg('execution', res.message, 'execution', undefined, res)
      } else {
        addMsg('assistant', res.message, res.type)
      }
      queryClient.invalidateQueries({ queryKey: ['ai-chat-history', sessionId] })
      queryClient.invalidateQueries({ queryKey: ['ai-chat-status', sessionId] })
    },
    onError: (err: any) => {
      setIsThinking(false)
      addMsg('system', `Erreur: ${err.message}`, 'error')
    },
  })

  const clearMut = useMutation({
    mutationFn: clearChat,
    onSuccess: () => {
      setMessages([])
      setPendingQuestions(null)
      queryClient.invalidateQueries({ queryKey: ['ai-chat-history', sessionId] })
    },
  })

  const addMsg = useCallback((
    role: DisplayMessage['role'],
    content: string,
    type?: string,
    questions?: string[],
    metadata?: Record<string, unknown>
  ) => {
    setMessages(prev => [...prev, {
      id: crypto.randomUUID(),
      role, content, type, questions, metadata,
      timestamp: new Date()
    }])
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isThinking])

  useEffect(() => {
    if (history?.messages) {
      const mapped: DisplayMessage[] = history.messages.map(m => ({
        id: `${m.timestamp}-${Math.random()}`,
        role: m.role as DisplayMessage['role'],
        content: m.content,
        type: m.metadata?.type as string,
        questions: m.metadata?.questions as string[],
        metadata: m.metadata as Record<string, unknown>,
        timestamp: new Date(m.timestamp),
      }))
      setMessages(mapped)
    }
  }, [history])

  const handleSend = () => {
    if (!input.trim() || chatMut.isPending) return
    addMsg('user', input)
    chatMut.mutate({
      message: input,
      session_id: sessionId,
      force_execute: forceExec,
    })
    setInput('')
    setForceExec(false)
  }

  const handleClarificationAnswer = (answer: string) => {
    addMsg('user', answer)
    chatMut.mutate({
      message: answer,
      session_id: sessionId,
      force_execute: true,
    })
    setPendingQuestions(null)
  }

  const quickCommands = [
    { icon: Wand2, label: 'Créer un module', text: 'Crée un module pour scanner les ports ouverts' },
    { icon: Code, label: 'Générer du code', text: 'Génère un endpoint API pour lister les credentials' },
    { icon: Box, label: 'Sandbox', text: 'Exécute un script nmap dans le sandbox et retourne les résultats en JSON' },
    { icon: Activity, label: 'Analyser', text: 'Analyse les dernières tâches et suggère des actions' },
    { icon: FileCode, label: 'Module PoC', text: 'Crée un module de PoC pour la technique MITRE T1021' },
    { icon: Sparkles, label: 'Améliorer Lucy', text: 'Améliore le dashboard avec un graphique de heatmap en temps réel' },
  ]

  const renderMessageContent = (msg: DisplayMessage) => {
    if (msg.type === 'execution_report') {
      return (
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-xs font-semibold text-success">
            <Check size={14} /> Rapport d'exécution
          </div>
          <ReactMarkdown
            className="prose prose-sm prose-invert max-w-none"
            components={{
              code({ node, inline, className, children, ...props }: any) {
                const match = /language-(\w+)/.exec(className || '')
                return !inline && match ? (
                  <SyntaxHighlighter style={vscDarkPlus} language={match[1]} PreTag="div" {...props}>
                    {String(children).replace(/\n$/, '')}
                  </SyntaxHighlighter>
                ) : (
                  <code className={className} {...props}>{children}</code>
                )
              }
            }}
          >
            {msg.content}
          </ReactMarkdown>
        </div>
      )
    }

    return (
      <ReactMarkdown
        className="prose prose-sm prose-invert max-w-none"
        components={{
          code({ node, inline, className, children, ...props }: any) {
            const match = /language-(\w+)/.exec(className || '')
            const codeString = String(children).replace(/\n$/, '')
            return !inline && match ? (
              <div className="relative">
                <div className="absolute top-1 right-1 flex gap-1">
                  <button
                    className="btn btn-xs btn-ghost btn-square"
                    onClick={() => navigator.clipboard.writeText(codeString)}
                    title="Copy"
                  >
                    <Copy size={12} />
                  </button>
                </div>
                <SyntaxHighlighter style={vscDarkPlus} language={match[1]} PreTag="div" {...props}>
                  {codeString}
                </SyntaxHighlighter>
              </div>
            ) : (
              <code className="bg-base-300 px-1 py-0.5 rounded text-xs font-mono" {...props}>{children}</code>
            )
          }
        }}
      >
        {msg.content}
      </ReactMarkdown>
    )
  }

  return (
    <PageTransition>
      <div className="page-container max-w-5xl h-[calc(100vh-6rem)] flex flex-col gap-4">
        {/* Header */}
        <div className="flex items-center justify-between shrink-0">
          <div className="space-y-1">
            <h1 className="text-2xl font-bold flex items-center gap-2">
              <Brain size={24} className="text-success animate-pulse" /> Lucy AI Architect
            </h1>
            <p className="text-sm text-base-content/50">
              Parle-moi en langage naturel. Je réfléchis, je clarifie, puis je construis.
            </p>
          </div>
          <div className="flex items-center gap-2">
            {status && (
              <div className={`badge badge-sm gap-1 ${
                status.status === 'executing' ? 'badge-warning' :
                status.status === 'clarifying' ? 'badge-info' :
                status.status === 'done' ? 'badge-success' : 'badge-ghost'
              }`}>
                {status.status === 'executing' && <Loader2 size={12} className="animate-spin" />}
                {status.status === 'clarifying' && <HelpCircle size={12} />}
                {status.status === 'done' && <Check size={12} />}
                {status.status}
              </div>
            )}
            <button
              className="btn btn-sm btn-ghost gap-1"
              onClick={() => clearMut.mutate(sessionId)}
              disabled={clearMut.isPending}
            >
              <RotateCcw size={14} /> Reset
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-4 gap-4 flex-1 min-h-0">
          {/* Chat Area */}
          <div className="lg:col-span-3 flex flex-col gap-3 min-h-0">
            <Card hover={false} className="flex-1 flex flex-col p-0 overflow-hidden min-h-0">
              {/* Messages */}
              <div className="flex-1 overflow-y-auto p-4 space-y-4">
                {messages.length === 0 && !historyLoading && (
                  <div className="text-center text-base-content/30 py-8 space-y-4">
                    <Brain size={48} className="mx-auto opacity-30" />
                    <div className="space-y-1">
                      <p className="text-sm font-medium">Je suis votre Architecte IA Lucy</p>
                      <p className="text-xs max-w-md mx-auto">
                        Décrivez ce que vous voulez en langage naturel. Je réfléchirai, vous poserai des questions si besoin,
                        puis je générerai le code, créerai les modules, et exécuterai dans le sandbox.
                      </p>
                    </div>

                    {/* Quick commands */}
                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 max-w-lg mx-auto mt-4">
                      {quickCommands.map((cmd, i) => (
                        <button
                          key={i}
                          className="btn btn-sm btn-outline gap-2 justify-start normal-case text-xs"
                          onClick={() => {
                            setInput(cmd.text)
                          }}
                        >
                          <cmd.icon size={14} />
                          {cmd.label}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {historyLoading && messages.length === 0 && (
                  <div className="flex items-center justify-center py-12">
                    <Loader2 size={24} className="animate-spin text-success" />
                  </div>
                )}

                <AnimatePresence>
                  {messages.map((msg) => (
                    <motion.div
                      key={msg.id}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      className={`flex ${
                        msg.role === 'user' ? 'justify-end' :
                        msg.role === 'system' ? 'justify-center' :
                        'justify-start'
                      }`}
                    >
                      {msg.role === 'system' ? (
                        <div className="badge badge-sm badge-ghost gap-1">
                          <AlertTriangle size={12} /> {msg.content}
                        </div>
                      ) : (
                        <div className={`max-w-[90%] rounded-xl p-3 space-y-2 ${
                          msg.role === 'user'
                            ? 'bg-success/15 text-success-content'
                            : msg.role === 'execution'
                              ? 'bg-warning/10 border border-warning/30'
                              : 'bg-base-300 text-base-content'
                        }`}>
                          <div className="flex items-center gap-2 text-[10px] opacity-60 uppercase font-semibold">
                            {msg.role === 'user' ? <MessageSquare size={10} /> :
                             msg.role === 'execution' ? <Zap size={10} className="text-warning" /> :
                             <Brain size={10} className="text-success" />}
                            {msg.role}
                          </div>
                          {renderMessageContent(msg)}

                          {/* Clarification questions */}
                          {msg.questions && msg.questions.length > 0 && (
                            <div className="space-y-2 mt-2">
                              <div className="text-xs font-semibold text-info flex items-center gap-1">
                                <HelpCircle size={12} /> Questions de clarification
                              </div>
                              <div className="space-y-1">
                                {msg.questions.map((q, i) => (
                                  <button
                                    key={i}
                                    className="btn btn-xs btn-outline btn-info w-full justify-start text-xs normal-case"
                                    onClick={() => handleClarificationAnswer(q)}
                                  >
                                    {i + 1}. {q}
                                  </button>
                                ))}
                              </div>
                              <p className="text-[10px] text-base-content/40">
                                Ou répondez librement dans le champ ci-dessous
                              </p>
                            </div>
                          )}

                          {/* Execution metadata */}
                          {msg.metadata && (msg.metadata.success_count !== undefined || msg.metadata.error_count !== undefined) && (
                            <div className="flex gap-2 mt-1">
                              {typeof msg.metadata.success_count === 'number' && (
                                <span className="text-[10px] text-success">{msg.metadata.success_count} succès</span>
                              )}
                              {typeof msg.metadata.error_count === 'number' && (
                                <span className="text-[10px] text-error">{msg.metadata.error_count} erreurs</span>
                              )}
                            </div>
                          )}
                        </div>
                      )}
                    </motion.div>
                  ))}
                </AnimatePresence>

                {/* Thinking indicator */}
                {isThinking && (
                  <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="flex justify-start"
                  >
                    <div className="bg-base-300 rounded-xl p-3 flex items-center gap-3">
                      <Loader2 size={16} className="animate-spin text-success" />
                      <div className="text-sm space-y-0.5">
                        <p className="font-medium">Réflexion en cours...</p>
                        <p className="text-xs text-base-content/50">
                          Analyse de la demande, recherche dans les ressources, planification
                        </p>
                      </div>
                    </div>
                  </motion.div>
                )}

                <div ref={bottomRef} />
              </div>

              {/* Input */}
              <div className="p-3 border-t border-base-300 shrink-0">
                <div className="flex gap-2">
                  <textarea
                    className="textarea textarea-bordered flex-1 min-h-[3rem] max-h-[8rem] text-sm resize-y"
                    placeholder="Décrivez ce que vous voulez... (ex: Crée un module qui scanne les ports 1-1000 et retourne un JSON)"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault()
                        handleSend()
                      }
                    }}
                    disabled={chatMut.isPending}
                  />
                  <div className="flex flex-col gap-1">
                    <button
                      className="btn btn-sm btn-success gap-1"
                      onClick={handleSend}
                      disabled={chatMut.isPending || !input.trim()}
                    >
                      {chatMut.isPending ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
                    </button>
                    <label className="label cursor-pointer gap-1 text-[10px] justify-center">
                      <input
                        type="checkbox"
                        className="checkbox checkbox-xs checkbox-warning"
                        checked={forceExec}
                        onChange={(e) => setForceExec(e.target.checked)}
                        title="Forcer l'exécution sans clarification"
                      />
                      <span className="opacity-70">Force</span>
                    </label>
                  </div>
                </div>
                <div className="flex gap-1 mt-2 flex-wrap">
                  {[
                    'analyse la situation',
                    'crée module portscan',
                    'génère API endpoint',
                    'exécute dans sandbox',
                    'suggère prochaines étapes',
                  ].map((cmd) => (
                    <button
                      key={cmd}
                      className="badge badge-sm badge-ghost cursor-pointer hover:badge-success text-xs"
                      onClick={() => setInput(cmd)}
                    >
                      {cmd}
                    </button>
                  ))}
                </div>
              </div>
            </Card>
          </div>

          {/* Sidebar Info */}
          <div className="space-y-3 shrink-0 overflow-y-auto">
            <Card hover={false} className="p-3 space-y-2">
              <h3 className="font-semibold text-xs flex items-center gap-1">
                <Activity size={12} className="text-success" /> Session
              </h3>
              <div className="space-y-1 text-xs">
                <div className="flex justify-between">
                  <span className="text-base-content/50">ID</span>
                  <span className="font-mono">{sessionId}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-base-content/50">Messages</span>
                  <span>{status?.message_count || 0}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-base-content/50">Plan</span>
                  <span>{status?.current_plan_steps || 0} étapes</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-base-content/50">Status</span>
                  <span className={`capitalize ${
                    status?.status === 'executing' ? 'text-warning' :
                    status?.status === 'done' ? 'text-success' :
                    status?.status === 'clarifying' ? 'text-info' : ''
                  }`}>{status?.status || 'idle'}</span>
                </div>
              </div>
            </Card>

            <Card hover={false} className="p-3 space-y-2">
              <h3 className="font-semibold text-xs flex items-center gap-1">
                <Terminal size={12} className="text-success" /> Comment ça marche
              </h3>
              <div className="space-y-2 text-xs text-base-content/70">
                <div className="flex gap-2">
                  <div className="badge badge-xs badge-success">1</div>
                  <span>Vous décrivez votre besoin</span>
                </div>
                <div className="flex gap-2">
                  <div className="badge badge-xs badge-info">2</div>
                  <span>Je réfléchis et clarifie si besoin</span>
                </div>
                <div className="flex gap-2">
                  <div className="badge badge-xs badge-warning">3</div>
                  <span>Je construis un plan d'exécution</span>
                </div>
                <div className="flex gap-2">
                  <div className="badge badge-xs badge-success">4</div>
                  <span>Je génère le code, teste, applique</span>
                </div>
              </div>
            </Card>

            <Card hover={false} className="p-3 space-y-2">
              <h3 className="font-semibold text-xs flex items-center gap-1">
                <Zap size={12} className="text-success" /> Capacités
              </h3>
              <div className="space-y-1 text-xs">
                <div className="flex items-center gap-1"><ChevronRight size={10} /> Créer des modules Python</div>
                <div className="flex items-center gap-1"><ChevronRight size={10} /> Générer des endpoints API</div>
                <div className="flex items-center gap-1"><ChevronRight size={10} /> Créer des composants React</div>
                <div className="flex items-center gap-1"><ChevronRight size={10} /> Exécuter dans sandbox</div>
                <div className="flex items-center gap-1"><ChevronRight size={10} /> Analyser les ressources Lucy</div>
                <div className="flex items-center gap-1"><ChevronRight size={10} /> Suggérer des techniques MITRE</div>
                <div className="flex items-center gap-1"><ChevronRight size={10} /> Auto-modifier Lucy</div>
              </div>
            </Card>
          </div>
        </div>
      </div>
    </PageTransition>
  )
}
