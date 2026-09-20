import { useState } from 'react'
import type { ChatTurn } from '../../types'

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

function percent(value: number): string {
  return `${Math.round(value * 100)}%`
}

function formatDate(value: string): string {
  try {
    return new Date(value).toLocaleDateString()
  } catch {
    return value
  }
}

export function MessageMeta({ turn, showMemorySources }: Props) {
  const [open, setOpen] = useState(false)

  return (
    <div className="bubble-meta">
      <button
        className="disclosure-toggle"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        aria-label="Toggle message details"
      >
        {open ? '▼' : '▶'} Details
        {turn.confidence && (
          <span
            className={`badge ${confidenceClass(turn.confidence.level)}`}
            style={{ marginLeft: 6 }}
          >
            {turn.confidence.level} {percent(turn.confidence.score)}
          </span>
        )}
      </button>

      {open && (
        <>
          {showMemorySources && turn.sources && turn.sources.length > 0 && (
            <div className="memory-source-list" style={{ marginTop: 8 }}>
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

          {turn.debug && turn.debug.retrieved.length > 0 && (
            <div className="memory-source-list" style={{ marginTop: 8 }}>
              <div className="muted" style={{ marginBottom: 4 }}>
                Debug: {turn.debug.retrieved.length} memories,{' '}
                {turn.debug.context_chars} chars
              </div>
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
        </>
      )}
    </div>
  )
}
