import type { MessageRecord } from '../../types'

interface Props {
  message: MessageRecord | undefined
  loading: boolean
}

function formatDate(value?: string | null): string {
  if (!value) return '\u2014'
  try { return new Date(value).toLocaleString() } catch { return value }
}

export default function MemorySource({ message, loading }: Props) {
  if (loading) return <div className="muted">Loading source message...</div>
  if (!message) return null

  return (
    <div className="source-card" style={{ marginTop: 6 }}>
      <div className="muted" style={{ fontSize: '0.7rem', marginBottom: 4 }}>
        {message.sender} &middot; {formatDate(message.timestamp)}
      </div>
      <div style={{ fontSize: '0.85rem' }}>{message.content}</div>
    </div>
  )
}
