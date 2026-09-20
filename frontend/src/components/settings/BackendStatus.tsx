import type { Health } from '../../types'

type Props = { health: Health | null; loading: boolean }

export function BackendStatus({ health, loading }: Props) {
  return (
    <section className="card" style={{ marginBottom: 16 }}>
      <h3 style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 12 }}>Backend status</h3>
      {loading && !health ? (
        <p className="muted">Loading backend status\u2026</p>
      ) : health ? (
        <div className="style-list">
          <li>Status: <span className={health.status === 'ok' ? 'status-ok' : 'status-bad'}>{health.status}</span></li>
          <li>App: <strong>{health.app}</strong> &middot; v{health.version}</li>
          <li>Active provider: {health.provider}</li>
          <li>
            Auth: <span className={health.provider_auth_configured ? 'status-ok' : 'status-bad'}>{health.provider_auth_configured ? 'configured' : 'not configured'}</span>
            <span className="muted"> chat {health.chat_auth_configured ? 'ok' : 'missing'} / embeddings {health.embedding_auth_configured ? 'ok' : 'missing'}</span>
          </li>
          {health.embedding_problems && health.embedding_problems.length > 0 && (
            <li className="status-bad">Embedding mismatch: {health.embedding_problems.length} problem(s) detected</li>
          )}
          <li>Vector store: <strong>{health.vector_store}</strong> ({health.vector_count} vectors)</li>
          <li>Stored: {health.counts.persons} people &middot; {health.counts.conversations} conversations &middot; {health.counts.messages} messages &middot; {health.counts.memories} memories</li>
        </div>
      ) : (
        <p className="muted">Backend unreachable.</p>
      )}
    </section>
  )
}
