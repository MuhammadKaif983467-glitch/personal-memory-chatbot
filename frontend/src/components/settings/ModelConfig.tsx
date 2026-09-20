import type { AppSettings } from '../../types'

type Props = { settings: AppSettings | null; loading: boolean }

export function ModelConfig({ settings, loading }: Props) {
  const isOffline = settings?.provider === 'mock' || settings?.provider === 'local'

  return (
    <section className="card">
      <h3 style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 12 }}>Model configuration</h3>
      {loading && !settings ? (
        <p className="muted">Loading configuration\u2026</p>
      ) : settings ? (
        <div className="style-list">
          <li>Provider mode: <strong>{settings.provider_mode}</strong> <span className="muted">(active: {settings.provider})</span></li>
          <li>Chat model: {isOffline ? <span className="muted">n/a (offline)</span> : settings.chat_model || <span className="muted">n/a</span>}</li>
          <li>Embedding model: {isOffline ? <span className="muted">hash embeddings (offline)</span> : settings.embedding_model || <span className="muted">n/a</span>}</li>
          <li>
            API key:{' '}
            <strong className={settings.api_key_configured ? 'status-ok' : 'status-bad'}>
              {settings.auth_status === 'configured' ? 'configured' : settings.auth_status === 'unavailable' ? 'offline mode' : 'not set'}
            </strong>
            {settings.split_keys_in_use && (
              <span className="muted"> (split: chat {settings.chat_key_configured ? <span className="status-ok">ok</span> : <span className="status-bad">missing</span>}, embeddings {settings.embedding_key_configured ? <span className="status-ok">ok</span> : <span className="status-bad">missing</span>})</span>
            )}{' '}
            <span className="muted">(value never displayed or sent to the browser)</span>
          </li>
          {!isOffline && (
            <li>Embeddings compatible: {settings.embedding_compatible ? <span className="status-ok">yes</span> : <span className="status-bad">no — re-embed required</span>}</li>
          )}
          <li>Memory min confidence: {settings.memory_min_confidence}</li>
          <li>Retrieval limit: {settings.retrieval_limit}</li>
          <li>Context budget: {settings.context_budget_chars} chars</li>
          <li>Consent required: {String(settings.consent_required)}</li>
        </div>
      ) : (
        <p className="muted">Model configuration unavailable.</p>
      )}
    </section>
  )
}
