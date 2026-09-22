import { useRef, useEffect } from 'react'
import type { ChatTurn } from '../../types'
import { Avatar } from '../ui/Avatar'
import { MessageBubble } from './MessageBubble'
import { EmptyConversation } from './EmptyConversation'

const GROUPING_WINDOW_MS = 2 * 60 * 1000

type Props = {
  turns: ChatTurn[]
  sending: boolean
  personName: string
  showMemorySources: boolean
  selectedPersonId: number | null
  activeConversationId: number | null
}

function isFirstInGroup(turns: ChatTurn[], index: number): boolean {
  if (index === 0) return true
  const prev = turns[index - 1]
  const curr = turns[index]
  if (prev.role !== curr.role) return true
  if (!prev.at || !curr.at) return true
  return curr.at - prev.at >= GROUPING_WINDOW_MS
}

function isLastInGroup(turns: ChatTurn[], index: number): boolean {
  if (index === turns.length - 1) return true
  const curr = turns[index]
  const next = turns[index + 1]
  if (curr.role !== next.role) return true
  if (!curr.at || !next.at) return true
  return next.at - curr.at >= GROUPING_WINDOW_MS
}

export function MessageList({
  turns,
  sending,
  personName,
  showMemorySources,
  selectedPersonId,
  activeConversationId,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = containerRef.current
    if (el) {
      requestAnimationFrame(() => { el.scrollTop = el.scrollHeight })
    }
  }, [turns, sending])

  if (turns.length === 0 && !sending) {
    return (
      <EmptyConversation
        personName={personName}
        hasPerson={selectedPersonId !== null}
        hasConversation={activeConversationId !== null}
      />
    )
  }

  return (
    <div className="transcript" ref={containerRef} role="log" aria-label="Conversation messages" aria-live="polite">
      {turns.map((t, i) => (
        <MessageBubble
          key={t.id}
          turn={t}
          showMemorySources={showMemorySources}
          isFirstInGroup={isFirstInGroup(turns, i)}
          isLastInGroup={isLastInGroup(turns, i)}
        />
      ))}

      {sending && (
        <div className="bubble-row bubble-assistant" role="status" aria-label="Assistant is typing">
          <Avatar name={personName || '?'} size="sm" />
          <div className="bubble">
            <div className="typing-indicator">
              <span className="typing-dot" />
              <span className="typing-dot" />
              <span className="typing-dot" />
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
