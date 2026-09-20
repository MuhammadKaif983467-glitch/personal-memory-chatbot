import type { VoiceStatus as VoiceStatusT } from '../../types'

type Props = { voice: VoiceStatusT | null }

export function VoiceStatusDisplay({ voice }: Props) {
  return (
    <section className="card" style={{ marginBottom: 16 }}>
      <h3 style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 12 }}>Voice</h3>
      {!voice ? (
        <p className="muted">Voice layer unavailable.</p>
      ) : voice.enabled ? (
        <p className="muted" style={{ marginBottom: 12 }}>Voice is enabled. Audio capture / playback lives in the browser.</p>
      ) : (
        <p className="muted" style={{ marginBottom: 12 }}>Voice is disabled by default. Enable it in backend settings (voice_enabled=true).</p>
      )}
      {voice && (
        <div className="style-list">
          <li>
            STT: <strong>{voice.stt.name}</strong>{' '}
            <span className={voice.stt.available ? 'status-ok' : 'status-bad'}>{voice.stt.available ? 'available' : 'unavailable'}</span>
            {voice.stt.error && <span className="muted"> &middot; {voice.stt.error}</span>}
          </li>
          <li>
            TTS: <strong>{voice.tts.name}</strong>{' '}
            <span className={voice.tts.available ? 'status-ok' : 'status-bad'}>{voice.tts.available ? 'available' : 'unavailable'}</span>
            {voice.tts.error && <span className="muted"> &middot; {voice.tts.error}</span>}
          </li>
          {voice.message && <li className="muted">{voice.message}</li>}
        </div>
      )}
    </section>
  )
}
