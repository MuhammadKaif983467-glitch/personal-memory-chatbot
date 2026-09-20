import { Avatar } from '../ui/Avatar'
import { MessageMeta } from './MessageMeta'
import type { ChatTurn } from '../../types'

type Props = {
  turn: ChatTurn
  showMemorySources: boolean
  isFirstInGroup: boolean
  isLastInGroup: boolean
}

function formatTime(value: number): string {
  return new Date(value).toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
  })
}

function outcomeStatus(outcome: string): string {
  const map: Record<string, string> = {
    remembered: 'status-active',
    updated: 'status-corrected',
    corrected: 'status-corrected',
    nothing_new: 'status-neutral',
    none: 'status-neutral',
    'no change': 'status-neutral',
  }
  return map[outcome] || 'status-neutral'
}

function outcomeLabel(outcome: string): string {
  const map: Record<string, string> = {
    remembered: 'Remembered',
    updated: 'Updated',
    corrected: 'Corrected',
    nothing_new: 'Nothing new',
    none: 'Nothing new',
    'no change': 'Nothing new',
  }
  return map[outcome] || outcome
}

export function MessageBubble({
  turn,
  showMemorySources,
  isFirstInGroup,
  isLastInGroup,
}: Props) {
  const isUser = turn.role === 'user'
  const speakerName = turn.speakerName || (isUser ? 'You' : 'Assistant')

  const hasMeta =
    turn.confidence ||
    (showMemorySources && turn.sources && turn.sources.length > 0) ||
    (turn.debug && turn.debug.retrieved.length > 0)

  return (
    <div className={`bubble-row ${isUser ? 'bubble-user' : 'bubble-assistant'}`}>
      {!isUser && (
        <div className="avatar-col">
          {isFirstInGroup ? (
            <Avatar name={speakerName} size="sm" className="avatar-person" />
          ) : (
            <div style={{ width: 28 }} />
          )}
        </div>
      )}

      <div className="bubble">
        {isFirstInGroup && (
          <div className="bubble-head">
            <span className="bubble-role">
              {isUser ? 'You' : speakerName}
            </span>
          </div>
        )}

        <div className="bubble-content">{turn.content}</div>

        {turn.memoryIndicator && (
          <div className="memory-hint">{turn.memoryIndicator}</div>
        )}

        {turn.learned && turn.learned.length > 0 && (
          <div className="learned">
            {turn.learned.map((lm, i) => (
              <div key={i} className="learned-item">
                <span className={`chip ${outcomeStatus(lm.outcome)}`}>
                  {outcomeLabel(lm.outcome)}
                </span>
                <span className="learned-content">{lm.content}</span>
              </div>
            ))}
          </div>
        )}

        {hasMeta && (
          <MessageMeta turn={turn} showMemorySources={showMemorySources} />
        )}

        {isLastInGroup && turn.at && (
          <div className="bubble-time-secondary">{formatTime(turn.at)}</div>
        )}
      </div>
    </div>
  )
}
