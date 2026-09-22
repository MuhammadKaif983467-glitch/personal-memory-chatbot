import { useState, useCallback, useEffect } from 'react'
import type { MemoryRelationship } from '../../types'
import { api, errText } from '../../services/api'

type Props = {
  memoryId: number
}

export function MemoryRelationships({ memoryId }: Props) {
  const [relationships, setRelationships] = useState<MemoryRelationship[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true); setError(null)
    try {
      const list = await api.listMemoryRelationships(memoryId)
      setRelationships(list)
    } catch (err) { setError(errText(err)) }
    finally { setLoading(false) }
  }, [memoryId])

  useEffect(() => { void load() }, [load])

  if (loading && relationships.length === 0) {
    return <div style={{ padding: '6px 0', fontSize: '0.75rem', color: 'var(--text-muted)' }}>Loading relationships...</div>
  }

  if (error) {
    return <div style={{ padding: '6px 0', fontSize: '0.75rem', color: 'var(--red)' }}>{error}</div>
  }

  if (relationships.length === 0) {
    return <div style={{ padding: '6px 0', fontSize: '0.75rem', color: 'var(--text-muted)' }}>No relationships</div>
  }

  return (
    <div style={{ padding: '6px 0' }}>
      <div style={{ fontSize: '0.7rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: 4, textTransform: 'uppercase' }}>
        Relationships ({relationships.length})
      </div>
      {relationships.map((r) => (
        <div key={r.id} style={{ fontSize: '0.8rem', padding: '4px 0', display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ fontSize: '0.7rem', padding: '2px 6px', borderRadius: 4, background: 'var(--accent-bg)', color: 'var(--accent)' }}>
            {r.relationship_type}
          </span>
          <span style={{ color: 'var(--text-muted)' }}>
            {r.source_content ? r.source_content.slice(0, 40) : `#${r.source_memory_id}`}
            {' \u2192 '}
            {r.target_content ? r.target_content.slice(0, 40) : `#${r.target_memory_id}`}
          </span>
          <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
            {Math.round(r.confidence * 100)}%
          </span>
        </div>
      ))}
    </div>
  )
}
