import { useCallback, useEffect, useState } from 'react'
import type { AppSettings, Health, VoiceStatus } from '../types'
import { api, errText } from '../services/api'
import type { Preferences } from '../services/preferences'

type Props = {
  preferences: Preferences
  onPreferences: (next: Preferences) => void
}

export function SettingsPanel({ preferences, onPreferences }: Props) {
  const [health, setHealth] = useState<Health | null>(null)
  const [settings, setSettings] = useState<AppSettings | null>(null)
  const [voice, setVoice] = useState<VoiceStatus | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [nextHealth, nextSettings, nextVoice] = await Promise.all([
        api.health(),
        api.getSettings(),
        api.voiceStatus().catch(() => null),
      ])
      setHealth(nextHealth)
      setSettings(nextSettings)
      setVoice(nextVoice)
    } catch (err) {
      setError(errText(err, 'Could not reach the backend.'))
      setHealth(null)
      setSettings(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const isOffline = settings?.provider === 'mock' || settings?.provider === 'local'

  return (
    <div className="panel">
      <header className="panel-head">
        <h2>Settings</h2>
        <button type="button" className="ghost" onClick={() => void load()} disabled={loading}>
          {loading ? 'Checking\u2026' : 'Recheck backend'}
        </button>
      </header>

      {error && <div className="error">{error}</div>}

      {/* ── Display preferences ─────────────────────────────────── */}
      <section className="card">
        <h3>Display preferences</h3>
        <p className="muted">Stored in this browser only.</p>
        <ul className="style-list">
          <li>
            <label className="toggle">
              <input
                type="checkbox"
                checked={preferences.showMemorySources}
                onChange={(e) =>
                  onPreferences({ ...preferences, showMemorySources: e.target.checked })
                }
              />
              <span className="toggle-track" />
              <span className="toggle-thumb" />
              <span>Memory disclosure: show which memories were used in each reply</span>
            </label>
          </li>
          <li>
            <label className="toggle">
              <input
                type="checkbox"
                checked={preferences.debugRetrieval}
                onChange={(e) =>
                  onPreferences({ ...preferences, debugRetrieval: e.target.checked })
                }
              />
              <span className="toggle-track" />
              <span className="toggle-thumb" />
              <span>Debug retrieval: show ranking details in each reply</span>
            </label>
          </li>
        </ul>
      </section>

      {/* ── Backend status ──────────────────────────────────────── */}
      <section className="card">
        <h3>Backend status</h3>
        {loading && !health ? (
          <p className="muted">Loading backend status\u2026</p>
        ) : health ? (
          <ul className="style-list">
            <li>
              Status:{' '}
              <span className={health.status === 'ok' ? 'status-ok' : 'status-bad'}>
                {health.status}
              </span>
            </li>
            <li>
              App: <strong>{health.app}</strong> &middot; v{health.version}
            </li>
            <li>Active provider: {health.provider}</li>
            <li>
              Auth:{' '}
              <span className={health.provider_auth_configured ? 'status-ok' : 'status-bad'}>
                {health.provider_auth_configured ? 'configured' : 'not configured'}
              </span>
              <span className="muted">
                {' '}chat {health.chat_auth_configured ? 'ok' : 'missing'} / embeddings{' '}
                {health.embedding_auth_configured ? 'ok' : 'missing'}
              </span>
            </li>
            {health.embedding_problems && health.embedding_problems.length > 0 && (
              <li className="status-bad">
                Embedding mismatch: {health.embedding_problems.length} problem(s) detected &mdash;
                re-embedding required
              </li>
            )}
            <li>
              Vector store: <strong>{health.vector_store}</strong> ({health.vector_count} vectors)
            </li>
            <li>
              Stored:{' '}
              {health.counts.persons} people &middot;{' '}
              {health.counts.conversations} conversations &middot;{' '}
              {health.counts.messages} messages &middot;{' '}
              {health.counts.memories} active memories
            </li>
          </ul>
        ) : (
          <p className="muted">Backend unreachable.</p>
        )}
      </section>

      {/* ── Voice ───────────────────────────────────────────────── */}
      <section className="card">
        <h3>Voice</h3>
        {voice ? (
          voice.enabled ? (
            <p className="muted" style={{ marginBottom: 12 }}>
              Voice is enabled. Audio capture / playback lives in the browser.
            </p>
          ) : (
            <p className="muted" style={{ marginBottom: 12 }}>
              Voice is disabled by default. Enable it in the backend settings
              (voice_enabled=true) to use speech-to-text and text-to-speech. The chat API always
              works with plain text regardless of voice state.
            </p>
          )
        ) : (
          <p className="muted" style={{ marginBottom: 12 }}>Voice layer unavailable.</p>
        )}
        {voice && (
          <ul className="style-list">
            <li>
              STT: <strong>{voice.stt.name}</strong>{' '}
              <span className={voice.stt.available ? 'status-ok' : 'status-bad'}>
                {voice.stt.available ? 'available' : 'unavailable'}
              </span>
              {voice.stt.error && <span className="muted"> &middot; {voice.stt.error}</span>}
            </li>
            <li>
              TTS: <strong>{voice.tts.name}</strong>{' '}
              <span className={voice.tts.available ? 'status-ok' : 'status-bad'}>
                {voice.tts.available ? 'available' : 'unavailable'}
              </span>
              {voice.tts.error && <span className="muted"> &middot; {voice.tts.error}</span>}
            </li>
            {voice.message && <li className="muted">{voice.message}</li>}
          </ul>
        )}
      </section>

      {/* ── Model configuration ─────────────────────────────────── */}
      <section className="card">
        <h3>Model configuration</h3>
        {loading && !settings ? (
          <p className="muted">Loading configuration\u2026</p>
        ) : settings ? (
          <ul className="style-list">
            <li>
              Provider mode: <strong>{settings.provider_mode}</strong>{' '}
              <span className="muted">(active: {settings.provider})</span>
            </li>
            <li>
              Chat model:{' '}
              {isOffline ? (
                <span className="muted">n/a (offline provider)</span>
              ) : (
                settings.chat_model || <span className="muted">n/a</span>
              )}
            </li>
            <li>
              Embedding model:{' '}
              {isOffline ? (
                <span className="muted">hash embeddings (offline)</span>
              ) : (
                settings.embedding_model || <span className="muted">n/a</span>
              )}
            </li>
            <li>
              API key:{' '}
              <strong className={settings.api_key_configured ? 'status-ok' : 'status-bad'}>
                {settings.auth_status === 'configured'
                  ? 'configured'
                  : settings.auth_status === 'unavailable'
                    ? 'offline mode'
                    : 'not set'}
              </strong>
              {settings.split_keys_in_use && (
                <span className="muted">
                  {' '}(split: chat{' '}
                  {settings.chat_key_configured ? (
                    <span className="status-ok">configured</span>
                  ) : (
                    <span className="status-bad">missing</span>
                  )}, embeddings{' '}
                  {settings.embedding_key_configured ? (
                    <span className="status-ok">configured</span>
                  ) : (
                    <span className="status-bad">missing</span>
                  )})
                </span>
              )}{' '}
              <span className="muted">(value never displayed or sent to the browser)</span>
            </li>
            {!isOffline && (
              <li>
                Embeddings compatible:{' '}
                {settings.embedding_compatible ? (
                  <span className="status-ok">yes</span>
                ) : (
                  <span className="status-bad">no &mdash; re-embed required</span>
                )}
              </li>
            )}
            <li>Memory min confidence: {settings.memory_min_confidence}</li>
            <li>Retrieval limit: {settings.retrieval_limit}</li>
            <li>Context budget: {settings.context_budget_chars} chars</li>
            <li>Recent messages in context: {settings.recent_conversation_messages}</li>
            <li>Consent required: {String(settings.consent_required)}</li>
            <li>Analyze on import: {String(settings.analyze_on_import)}</li>
          </ul>
        ) : (
          <p className="muted">Model configuration unavailable.</p>
        )}
      </section>
    </div>
  )
}
