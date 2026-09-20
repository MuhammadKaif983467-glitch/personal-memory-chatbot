import type { MemoryVersion } from '../../types'

interface Props {
  versions: MemoryVersion[] | undefined
  loading: boolean
}

function formatDate(value?: string | null): string {
  if (!value) return '\u2014'
  try { return new Date(value).toLocaleString() } catch { return value }
}

export default function MemoryHistory({ versions, loading }: Props) {
  return (
    <div className="versions">
      <div className="muted" style={{ fontSize: '0.75rem', marginBottom: 6, fontWeight: 600 }}>Version History</div>
      {loading && <div className="muted" style={{ fontSize: '0.75rem' }}>Loading...</div>}
      {!loading && versions && versions.length === 0 && (
        <div className="muted" style={{ fontSize: '0.75rem' }}>No history available.</div>
      )}
      {!loading && versions && versions.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {versions.map(v => (
            <div key={v.id} className="source-card" style={{ borderLeft: `3px solid ${v.status === 'active' ? 'var(--green)' : 'var(--yellow)'}` }}>
              <div className="row" style={{ gap: 6, fontSize: '0.7rem', marginBottom: 4, flexWrap: 'wrap' }}>
                <span className="muted">Rev {v.revision}</span>
                <span className={`chip chip-${v.status === 'active' ? 'active' : 'corrected'}`}>{v.status}</span>
                <span className="muted">{v.memory_type}</span>
                <span className="muted">by {v.actor}</span>
                <span className="muted" style={{ marginLeft: 'auto' }}>{formatDate(v.created_at)}</span>
              </div>
              <div style={{ fontSize: '0.8rem' }}>{v.content}</div>
              {v.note && <div className="muted" style={{ fontSize: '0.7rem', marginTop: 2, fontStyle: 'italic' }}>Note: {v.note}</div>}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
