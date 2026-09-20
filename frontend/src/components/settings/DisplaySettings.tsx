import type { Preferences } from '../../services/preferences'

type Props = { preferences: Preferences; onPreferences: (next: Preferences) => void }

export function DisplaySettings({ preferences, onPreferences }: Props) {
  return (
    <section className="card" style={{ marginBottom: 16 }}>
      <h3 style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 12 }}>Display preferences</h3>
      <p className="muted" style={{ fontSize: '0.8rem', marginBottom: 12 }}>Stored in this browser only.</p>
      <div className="style-list">
        <li>
          <label className="toggle">
            <input type="checkbox" checked={preferences.showMemorySources} onChange={(e) => onPreferences({ ...preferences, showMemorySources: e.target.checked })} />
            <span className="toggle-track" /><span className="toggle-thumb" />
            <span>Memory disclosure: show which memories were used in each reply</span>
          </label>
        </li>
        <li>
          <label className="toggle">
            <input type="checkbox" checked={preferences.debugRetrieval} onChange={(e) => onPreferences({ ...preferences, debugRetrieval: e.target.checked })} />
            <span className="toggle-track" /><span className="toggle-thumb" />
            <span>Debug retrieval: show ranking details in each reply</span>
          </label>
        </li>
      </div>
    </section>
  )
}
