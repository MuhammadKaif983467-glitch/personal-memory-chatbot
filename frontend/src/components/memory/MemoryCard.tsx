import type { Memory, MemoryVersion, MessageRecord } from '../../types'
import MemoryEditor from './MemoryEditor'
import MemoryCorrectionEditor from './MemoryCorrectionEditor'
import MemoryHistory from './MemoryHistory'
import MemorySource from './MemorySource'
import { MemoryRelationships } from './MemoryRelationships'

interface Props {
  memory: Memory
  editingId: number | null
  correctingId: number | null
  editContent: string
  correctContent: string
  expandedVersions: Set<number>
  versionCache: Record<number, MemoryVersion[]>
  expandedSource: Set<number>
  sourceCache: Record<number, MessageRecord>
  expandedRelationships: Set<number>
  onEditContentChange: (v: string) => void
  onCorrectContentChange: (v: string) => void
  onSaveEdit: (id: number) => void
  onSaveCorrect: (id: number) => void
  onCancelEdit: () => void
  onCancelCorrect: () => void
  onStartEdit: (id: number, content: string) => void
  onStartCorrect: (id: number, content: string) => void
  onToggleVersions: (id: number) => void
  onToggleSource: (msgId: number) => void
  onDelete: (id: number) => void
  onToggleRelationships: (id: number) => void
  personName: (id: number) => string
}

function formatShortDate(value?: string | null): string {
  if (!value) return '\u2014'
  try { return new Date(value).toLocaleDateString() } catch { return value }
}

export default function MemoryCard({
  memory, editingId, correctingId, editContent, correctContent,
  expandedVersions, versionCache, expandedSource, sourceCache,
  expandedRelationships,
  onEditContentChange, onCorrectContentChange, onSaveEdit, onSaveCorrect,
  onCancelEdit, onCancelCorrect, onStartEdit, onStartCorrect,
  onToggleVersions, onToggleSource, onDelete, onToggleRelationships, personName,
}: Props) {
  const m = memory
  const chipClass = (t: string) => `chip chip-${t.toLowerCase()}`
  const busy = editingId === m.id || correctingId === m.id

  return (
    <div className="memory-card">
      <div className="memory-top">
        <span className={chipClass(m.memory_type)}>{m.memory_type}</span>
        <span className={`chip chip-${m.status === 'active' ? 'active' : 'corrected'}`}>{m.status}</span>
        <span className="muted" style={{ fontSize: '0.75rem' }}>{m.person_name || personName(m.person_id)}</span>
      </div>

      {editingId === m.id ? (
        <MemoryEditor content={editContent} onChange={onEditContentChange} onSave={() => onSaveEdit(m.id)} onCancel={onCancelEdit} />
      ) : correctingId === m.id ? (
        <MemoryCorrectionEditor content={correctContent} onChange={onCorrectContentChange} onSave={() => onSaveCorrect(m.id)} onCancel={onCancelCorrect} />
      ) : (
        <div className="memory-content">{m.content}</div>
      )}

      <div className="memory-source-meta" style={{ marginTop: 8 }}>
        <span className="muted">Confidence: {Math.round(m.confidence * 100)}%</span>
        <span className="muted">Importance: {Math.round(m.importance * 100)}%</span>
        <span className="muted">Created: {formatShortDate(m.created_at)}</span>
      </div>

      {m.source_message_id && (
        <div style={{ marginTop: 8 }}>
          <button className="disclosure-toggle" onClick={() => onToggleSource(m.source_message_id!)}>
            {expandedSource.has(m.source_message_id) ? '\u25BC' : '\u25B6'} Source message
          </button>
          {expandedSource.has(m.source_message_id) && (
            <MemorySource message={sourceCache[m.source_message_id]} loading={!sourceCache[m.source_message_id]} />
          )}
        </div>
      )}

      {m.note && <div className="muted" style={{ fontSize: '0.75rem', marginTop: 4, fontStyle: 'italic' }}>Note: {m.note}</div>}

      <div className="row" style={{ gap: 4, marginTop: 8 }}>
        <button className="btn btn-ghost" style={{ padding: '3px 10px', fontSize: '0.75rem' }} onClick={() => onStartCorrect(m.id, m.content)} disabled={busy}>
          Correct
        </button>
        <button className="btn btn-ghost" style={{ padding: '3px 10px', fontSize: '0.75rem' }} onClick={() => onStartEdit(m.id, m.content)} disabled={busy}>
          Edit
        </button>
        <button className="btn btn-ghost" style={{ padding: '3px 10px', fontSize: '0.75rem' }} onClick={() => onToggleVersions(m.id)}>
          {expandedVersions.has(m.id) ? 'Hide history' : 'History'}
        </button>
        <button className="btn btn-ghost" style={{ padding: '3px 10px', fontSize: '0.75rem' }} onClick={() => onToggleRelationships(m.id)}>
          {expandedRelationships.has(m.id) ? 'Hide links' : 'Links'}
        </button>
        <button className="btn btn-danger" style={{ padding: '3px 10px', fontSize: '0.75rem' }} onClick={() => onDelete(m.id)} disabled={busy}>
          Delete
        </button>
      </div>

      {expandedVersions.has(m.id) && (
        <MemoryHistory versions={versionCache[m.id]} loading={!versionCache[m.id]} />
      )}

      {expandedRelationships.has(m.id) && (
        <MemoryRelationships memoryId={m.id} />
      )}
    </div>
  )
}
