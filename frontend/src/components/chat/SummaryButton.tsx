import { useState, useCallback } from 'react'
import type { SummaryInfo } from '../../types'
import { api, errText } from '../../services/api'

type Props = {
  conversationId: number | null
  projectId?: number | null
}

export function SummaryButton({ conversationId, projectId }: Props) {
  const [summary, setSummary] = useState<SummaryInfo | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [expanded, setExpanded] = useState(false)

  const handleToggle = useCallback(async () => {
    if (expanded) { setExpanded(false); return }
    if (summary) { setExpanded(true); return }
    if (!conversationId) return

    setLoading(true); setError(null)
    try {
      const s = await api.getSummary(conversationId)
      setSummary(s)
      setExpanded(true)
    } catch {
      // No summary available — try generating
      try {
        const s = await api.generateSummary(conversationId, projectId ?? undefined)
        setSummary(s)
        setExpanded(true)
      } catch (err) {
        setError(errText(err, 'No summary available'))
      }
    } finally { setLoading(false) }
  }, [conversationId, projectId, expanded, summary])

  if (!conversationId) return null

  return (
    <div style={{ position: 'relative', display: 'inline-block' }}>
      <button
        type="button"
        className="btn btn-ghost"
        style={{ padding: '4px 8px', fontSize: '0.75rem' }}
        onClick={() => void handleToggle()}
        disabled={loading}
        title="View conversation summary"
      >
        {loading ? '...' : expanded ? 'Hide summary' : 'Summary'}
      </button>
      {error && (
        <div style={{ position: 'absolute', top: '100%', right: 0, zIndex: 20, background: 'var(--surface-elevated)', border: '1px solid var(--border-subtle)', borderRadius: 6, padding: '8px 12px', fontSize: '0.8rem', color: 'var(--red)', maxWidth: 300, boxShadow: '0 4px 12px rgba(0,0,0,0.15)' }} onClick={() => setError(null)}>
          {error}
        </div>
      )}
      {expanded && summary && (
        <div style={{ position: 'absolute', top: '100%', right: 0, zIndex: 20, background: 'var(--surface-elevated)', border: '1px solid var(--border-subtle)', borderRadius: 6, padding: '12px 14px', fontSize: '0.8rem', maxWidth: 400, maxHeight: 300, overflowY: 'auto', boxShadow: '0 4px 12px rgba(0,0,0,0.15)', lineHeight: 1.5 }}>
          <div style={{ fontWeight: 600, marginBottom: 4 }}>Summary ({summary.message_count} messages)</div>
          <div style={{ whiteSpace: 'pre-wrap' }}>{summary.summary}</div>
          {summary.version > 1 && (
            <div style={{ marginTop: 6, fontSize: '0.7rem', color: 'var(--text-muted)' }}>Version {summary.version}</div>
          )}
        </div>
      )}
    </div>
  )
}
