import { useState } from 'react'
import { Bot, User, Radio, Terminal, Server, Waves } from 'lucide-react'
import type { ChatMessage as ChatMessageType } from '../types/chat'

interface ChatMessageProps {
  message: ChatMessageType
  /** When set, overrides message.content with live-streaming text. */
  streamingText?: string
}

const OS_EMOJI: Record<string, string> = { windows: '🪟', linux: '🐧', darwin: '🍎' }

function getOsEmoji(osOrHostname?: string): string {
  if (!osOrHostname) return '🖥️'
  const lower = osOrHostname.toLowerCase()
  if (lower.includes('win')) return OS_EMOJI.windows
  if (lower.includes('darwin') || lower.includes('mac')) return OS_EMOJI.darwin
  if (lower.includes('linux') || lower.includes('ubuntu') || lower.includes('debian')) return OS_EMOJI.linux
  return '🖥️'
}

const roleIcons: Record<string, React.ReactNode> = {
  assistant: <Bot size={18} />,
  user: <User size={18} />,
  event: <Radio size={18} />,
  system: <Terminal size={18} />,
}

const roleClasses: Record<string, string> = {
  assistant: 'chat-bubble-success',
  user: 'chat-bubble-primary',
  event: 'chat-bubble-info',
  system: 'chat-bubble-warning',
}

export default function ChatMessage({ message, streamingText }: ChatMessageProps) {
  const [showRaw, setShowRaw] = useState(false)

  const mood = (message.metadata?.mood as string) || 'calm'
  const isEvent = message.role === 'event'
  const isAgent = isEvent && !!message.agent_id
  const agentName = message.hostname || (message.agent_id ? `Agent ${message.agent_id.slice(0, 8)}` : 'Agent')
  const isShannon = message.metadata?.shannon || message.source_event_type === 'shannon_stream'
  const displayContent = streamingText !== undefined ? streamingText : message.content
  const isStreaming = streamingText !== undefined && streamingText.length === 0

  return (
    <div className={`chat ${message.role === 'user' ? 'chat-end' : 'chat-start'} mb-2`}>
      <div className="chat-image avatar">
        <div className={`w-8 h-8 rounded-full flex items-center justify-center text-base-content ${
          isAgent ? 'bg-success/15' : isShannon ? 'bg-info/15 text-info' : 'bg-base-300'
        }`}>
          {isAgent ? (
            <span className="text-base">{getOsEmoji(message.hostname || undefined)}</span>
          ) : isShannon ? (
            <Waves size={16} className="animate-pulse" />
          ) : (
            roleIcons[message.role] || roleIcons.system
          )}
        </div>
      </div>
      <div className="chat-header text-xs text-base-content/60 mb-1">
        {isShannon && <span className="font-semibold text-info flex items-center gap-1 inline-flex"><Waves size={10} /> ShannonAi</span>}
        {!isShannon && message.role === 'assistant' && 'Lucy'}
        {message.role === 'user' && 'You'}
        {isAgent && (
          <span className="font-semibold text-success flex items-center gap-1 inline-flex">
            <Server size={10} /> {agentName}
          </span>
        )}
        {isEvent && !isAgent && `Event · ${message.source_event_type || 'unknown'}`}
        {message.role === 'system' && 'System'}
        {mood && !isAgent && !isShannon && (
          <span className="ml-2 capitalize opacity-70">({mood})</span>
        )}
        <time className="ml-2 text-xs">
          {new Date(message.created_at).toLocaleTimeString()}
        </time>
      </div>
      <div className={`chat-bubble ${isShannon ? 'chat-bubble-info' : roleClasses[message.role] || roleClasses.system} text-sm`}>
        {isStreaming ? (
          <p className="whitespace-pre-wrap opacity-60 italic">Composing narrative…</p>
        ) : (
          <p className="whitespace-pre-wrap">
            {displayContent}
            {streamingText !== undefined && <span className="animate-pulse">▋</span>}
          </p>
        )}
        {(message.raw_payload || isEvent) && (
          <button
            type="button"
            onClick={() => setShowRaw((v) => !v)}
            className="text-xs underline mt-1 opacity-70 hover:opacity-100"
          >
            {showRaw ? 'Hide raw' : 'Show raw'}
          </button>
        )}
        {showRaw && message.raw_payload && (
          <pre className="mt-2 p-2 rounded bg-black/20 text-xs overflow-x-auto">
            {JSON.stringify(message.raw_payload, null, 2)}
          </pre>
        )}
      </div>
    </div>
  )
}
