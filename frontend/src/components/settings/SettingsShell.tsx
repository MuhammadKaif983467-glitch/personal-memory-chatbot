import { useCallback, useEffect, useState } from 'react'
import type { AppSettings, Health, VoiceStatus } from '../../types'
import { api, errText } from '../../services/api'
import type { Preferences } from '../../services/preferences'
import { DisplaySettings } from './DisplaySettings'
import { BackendStatus } from './BackendStatus'
import { VoiceStatusDisplay } from './VoiceStatus'
import { ModelConfig } from './ModelConfig'

type Props = { preferences: Preferences; onPreferences: (next: Preferences) => void }

export function SettingsShell({ preferences, onPreferences }: Props) {
  const [health, setHealth] = useState<Health | null>(null)
  const [settings, setSettings] = useState<AppSettings | null>(null)
  const [voice, setVoice] = useState<VoiceStatus | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const load = useCallback(async () => {
    setLoading(true); setError(null)
    try {
      const [h, s, v] = await Promise.all([api.health(), api.getSettings(), api.voiceStatus().catch(() => null)])
      setHealth(h); setSettings(s); setVoice(v)
    } catch (err) { setError(errText(err, 'Could not reach the backend.')); setHealth(null); setSettings(null) }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { void load() }, [load])

  return (
    <div className="panel">
      <header className="panel-head" style={{ background: 'transparent', borderBottom: '1px solid var(--border-subtle)' }}>
        <div className="row-between">
          <div>
            <h2 style={{ fontSize: '1.1rem', fontWeight: 700, margin: 0 }}>Settings</h2>
            <p className="muted" style={{ fontSize: '0.85rem', marginTop: 4 }}>Backend status, model configuration, and display preferences</p>
          </div>
          <button className="btn btn-ghost" onClick={() => void load()} disabled={loading}>{loading ? 'Checking...' : 'Recheck'}</button>
        </div>
      </header>
      {error && <div className="error" onClick={() => setError(null)}>{error}</div>}
      <DisplaySettings preferences={preferences} onPreferences={onPreferences} />
      <BackendStatus health={health} loading={loading} />
      <VoiceStatusDisplay voice={voice} />
      <ModelConfig settings={settings} loading={loading} />
    </div>
  )
}
