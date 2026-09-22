import { useState, useCallback, useEffect } from 'react'
import type { BackupInfo } from '../../types'
import { api, errText } from '../../services/api'

export function BackupPanel() {
  const [backups, setBackups] = useState<BackupInfo[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)
  const [restoring, setRestoring] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true); setError(null)
    try {
      const list = await api.listBackups()
      setBackups(list)
    } catch (err) { setError(errText(err)) }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { void load() }, [load])

  const handleCreate = useCallback(async () => {
    setCreating(true); setError(null)
    try {
      await api.createBackup()
      void load()
    } catch (err) { setError(errText(err)) }
    finally { setCreating(false) }
  }, [load])

  const handleRestore = useCallback(async (path: string) => {
    setRestoring(path); setError(null)
    try {
      await api.restoreBackup(path)
      setRestoring(null)
    } catch (err) { setError(errText(err)); setRestoring(null) }
  }, [])

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  return (
    <div style={{ padding: '16px', borderTop: '1px solid var(--border-subtle)' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <h3 style={{ fontSize: '0.95rem', fontWeight: 600, margin: 0 }}>Backups</h3>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn btn-ghost" onClick={() => void load()} disabled={loading}>
            {loading ? 'Loading...' : 'Refresh'}
          </button>
          <button className="btn btn-primary" onClick={() => void handleCreate()} disabled={creating}>
            {creating ? 'Creating...' : 'New Backup'}
          </button>
        </div>
      </div>
      {error && <div className="error" onClick={() => setError(null)}>{error}</div>}
      {backups.length === 0 && !loading && (
        <div style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>No backups yet</div>
      )}
      {backups.map((b) => (
        <div key={b.path} style={{
          padding: '10px 12px', border: '1px solid var(--border-subtle)', borderRadius: 6,
          marginBottom: 8, fontSize: '0.85rem',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <span style={{ fontWeight: 500 }}>{b.created_at ? new Date(b.created_at).toLocaleString() : b.path}</span>
              <span style={{ marginLeft: 8, color: 'var(--text-muted)' }}>{formatSize(b.size)}</span>
              {!b.valid && <span style={{ marginLeft: 8, color: 'var(--red)', fontWeight: 500 }}>Invalid</span>}
            </div>
            <button
              className="btn btn-ghost"
              style={{ padding: '4px 8px', fontSize: '0.75rem' }}
              onClick={() => void handleRestore(b.path)}
              disabled={restoring === b.path}
            >
              {restoring === b.path ? 'Restoring...' : 'Restore'}
            </button>
          </div>
          {(b.message_count > 0 || b.memory_count > 0) && (
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: 4 }}>
              {b.message_count} messages &middot; {b.memory_count} memories
            </div>
          )}
          {b.errors.length > 0 && (
            <div style={{ fontSize: '0.75rem', color: 'var(--red)', marginTop: 4 }}>
              {b.errors.join(', ')}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
