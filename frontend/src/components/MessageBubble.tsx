import { useState } from 'react'
import type { ChatTurn } from '../types'

type Props = {
  turn: ChatTurn
  showMemorySources: boolean
}

function confidenceClass(level: string): string {
  const map: Record<string, string> = {
    high: 'badge-high',
    medium: 'badge-medium',
    low: 'badge-low',
    very_high: 'badge-high',
    very_low: 'badge-low',
  }
  return map[level] || 'badge-medium'
}

function formatTime(value: number): string {
  const d = new Date(value)
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

function formatDate(value: string): string {
  try {
    return new Date(value).toLocaleDateString()
  } catch {
    return value
  }
}

function percent(value: number): string {
  return `${Math.round(value * 100)}%`
}

function outcomeStatus(outcome: string): string {
  const map: Record<string, string> = {
    remembered: 'status-active',
    updated: 'status-corrected',
    corrected: 'status-corrected',
    none: 'status-neutral',
    'no change': 'status-neutral',
    nothing_new: 'status-neutral',
  }
  return map[outcome] || 'status-neutral'
}

function outcomeLabel(outcome: string): string {
  const map: Record<string, string> = {
    remembered: 'Remembered',
    updated: 'Updated',
    corrected: 'Corrected',
    none: 'Nothing new',
    'no change': 'Nothing new',
    nothing_new: 'Nothing new',
  }
  return map[outcome] || outcome
}

export function MessageBubble({ turn, showMemorySources }: Props) {
  const [sourcesOpen, setSourcesOpen] = useState(false)
  const [debugOpen, setDebugOpen] = useState(false)

  const isUser = turn.role === 'user'

  return (
    <div className={`bubble-row ${isUser ? 'bubble-user' : 'bubble-assistant'}`}>
      <div className="bubble fadeInUp">
        <div className="bubble-head">
          <span className="bubble-role">{isUser ? 'You' : 'Assistant'}</span>
          {turn.confidence && (
            <span className={`badge ${confidenceClass(turn.confidence.level)}`}>
              {turn.confidence.level} {percent(turn.confidence.score)}
            </span>
          )}
          {turn.at && <span className="bubble-time">{formatTime(turn.at)}</span>}
        </div>

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

        {showMemorySources && turn.sources && turn.sources.length > 0 && (
          <div className="sources">
            <button
              className="disclosure-toggle"
              onClick={() => setSourcesOpen(!sourcesOpen)}
            >
              {sourcesOpen ? '▼' : '▶'} Source memories ({turn.sources.length})
            </button>
            {sourcesOpen && (
              <div className="memory-source-list">
                {turn.sources.map((src) => (
                  <div key={src.memory_id} className="memory-source">
                    <div className="memory-source-top">
                      <span className="chip">{src.memory_type}</span>
                      <span className={`chip status-${src.status}`}>
                        {src.status}
                      </span>
                      <span className="muted">#{src.memory_id}</span>
                    </div>
                    <div className="memory-source-content">{src.content}</div>
                    <div className="memory-source-meta">
                      <span>Confidence {percent(src.confidence)}</span>
                      <span>Importance {percent(src.importance)}</span>
                      {src.source_timestamp && (
                        <span>{formatDate(src.source_timestamp)}</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {turn.debug && turn.debug.retrieved.length > 0 && (
          <div className="sources">
            <button
              className="disclosure-toggle"
              onClick={() => setDebugOpen(!debugOpen)}
            >
              {debugOpen ? '▼' : '▶'} Debug: retrieval ({turn.debug.retrieved.length} memories,{' '}
              {turn.debug.context_chars} chars)
            </button>
            {debugOpen && (
              <div className="memory-source-list">
                {turn.debug.retrieved.map((rm) => (
                  <div key={rm.memory_id} className="memory-source">
                    <div className="memory-source-top">
                      <span className="chip">{rm.memory_type}</span>
                      <span className="muted">#{rm.memory_id}</span>
                      <span>rank {rm.rank}</span>
                      <span>sim {percent(rm.similarity)}</span>
                    </div>
                    <div className="memory-source-content">{rm.content}</div>
                    <div className="memory-source-meta">
                      <span>Confidence {percent(rm.confidence)}</span>
                      {rm.source_timestamp && (
                        <span>{formatDate(rm.source_timestamp)}</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
