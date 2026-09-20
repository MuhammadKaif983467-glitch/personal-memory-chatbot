import { useState, useEffect, useCallback, useRef } from 'react'
import type { Memory, MemoryVersion, MessageRecord, Person } from '../types'

type MemoryType = Memory['memory_type']

const MEMORY_TYPES: MemoryType[] = ['FACT', 'PREFERENCE', 'INTEREST', 'RELATIONSHIP', 'EVENT', 'HABIT', 'OPINION', 'CONVERSATION', 'TEMPORARY']
const STATUS_OPTIONS = [
  { value: 'active', label: 'Current only' },
  { value: 'corrected', label: 'Superseded / corrected' },
  { value: 'all', label: 'All (audit)' },
]

function formatDate(value?: string | null): string {
  if (!value) return '\u2014'
  try { return new Date(value).toLocaleString() } catch { return value }
}

function formatShortDate(value?: string | null): string {
  if (!value) return '\u2014'
  try { return new Date(value).toLocaleDateString() } catch { return value }
}

interface Props {
  persons: Person[]
  selectedPersonId: number | null
  onSelectPerson: (id: number | null) => void
}

export default function MemoryPanel({ persons, selectedPersonId, onSelectPerson }: Props) {
  const [memories, setMemories] = useState<Memory[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  const [searchQuery, setSearchQuery] = useState('')
  const [filterType, setFilterType] = useState('')
  const [filterStatus, setFilterStatus] = useState('active')

  const [newContent, setNewContent] = useState('')
  const [newType, setNewType] = useState<MemoryType>('FACT')

  const [editingId, setEditingId] = useState<number | null>(null)
  const [editContent, setEditContent] = useState('')
  const [correctingId, setCorrectingId] = useState<number | null>(null)
  const [correctContent, setCorrectContent] = useState('')
  const [expandedVersions, setExpandedVersions] = useState<Set<number>>(new Set())
  const [versionCache, setVersionCache] = useState<Record<number, MemoryVersion[]>>({})
  const [sourceCache, setSourceCache] = useState<Record<number, MessageRecord>>({})
  const [expandedSource, setExpandedSource] = useState<Set<number>>(new Set())

  const editRef = useRef<HTMLTextAreaElement | null>(null)
  const correctRef = useRef<HTMLTextAreaElement | null>(null)

  const fetchMemories = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const params: Record<string, unknown> = { status: filterStatus }
      if (selectedPersonId) params.personId = selectedPersonId
      if (filterType) params.memoryType = filterType
      if (searchQuery.trim()) params.queryText = searchQuery.trim()
      const res = await (window as any).api.listMemories(params)
      setMemories(res ?? [])
    } catch (e: any) {
      setError(e?.message ?? 'Failed to load memories')
    } finally {
      setLoading(false)
    }
  }, [selectedPersonId, filterType, filterStatus, searchQuery])

  useEffect(() => { fetchMemories() }, [fetchMemories])

  useEffect(() => {
    if (editingId && editRef.current) { editRef.current.focus(); editRef.current.select() }
  }, [editingId])
  useEffect(() => {
    if (correctingId && correctRef.current) { correctRef.current.focus(); correctRef.current.select() }
  }, [correctingId])

  const clearMessages = () => { setError(null); setNotice(null) }
  const flash = (msg: string) => { setNotice(msg); setTimeout(() => setNotice(null), 4000) }

  const handleAdd = async () => {
    if (!newContent.trim() || !selectedPersonId) return
    clearMessages()
    try {
      await (window as any).api.createMemory({ person_id: selectedPersonId, content: newContent.trim(), memory_type: newType })
      setNewContent('')
      flash('Memory added')
      fetchMemories()
    } catch (e: any) { setError(e?.message ?? 'Failed to add memory') }
  }

  const handleSaveEdit = async (id: number) => {
    clearMessages()
    try {
      await (window as any).api.editMemory(id, editContent.trim())
      setEditingId(null); setEditContent(''); flash('Memory updated'); fetchMemories()
    } catch (e: any) { setError(e?.message ?? 'Failed to update') }
  }

  const handleSaveCorrect = async (id: number) => {
    clearMessages()
    try {
      await (window as any).api.correctMemory(id, { content: correctContent.trim() })
      setCorrectingId(null); setCorrectContent(''); flash('Memory corrected'); fetchMemories()
    } catch (e: any) { setError(e?.message ?? 'Failed to correct') }
  }

  const handleDelete = async (id: number) => {
    if (!confirm('Delete this memory permanently?')) return
    clearMessages()
    try {
      await (window as any).api.deleteMemory(id); flash('Memory deleted'); fetchMemories()
    } catch (e: any) { setError(e?.message ?? 'Failed to delete') }
  }

  const toggleVersions = async (id: number) => {
    const next = new Set(expandedVersions)
    if (next.has(id)) { next.delete(id); setExpandedVersions(next); return }
    next.add(id); setExpandedVersions(next)
    if (!versionCache[id]) {
      try {
        const vers = await (window as any).api.getMemoryVersions(id)
        setVersionCache(prev => ({ ...prev, [id]: vers ?? [] }))
      } catch (e: any) { setError(e?.message ?? 'Failed to load history') }
    }
  }

  const toggleSource = async (msgId: number) => {
    const next = new Set(expandedSource)
    if (next.has(msgId)) { next.delete(msgId); setExpandedSource(next); return }
    next.add(msgId); setExpandedSource(next)
    if (!sourceCache[msgId]) {
      try {
        const msg = await (window as any).api.getMessage(msgId)
        setSourceCache(prev => ({ ...prev, [msgId]: msg }))
      } catch (e: any) { setError(e?.message ?? 'Failed to load source message') }
    }
  }

  const personName = (id: number) => persons.find(p => p.id === id)?.name ?? `Person #${id}`
  const chipClass = (t: string) => `chip chip-${t.toLowerCase()}`
  const statusClass = (s: string) => `chip status-${s}`

  return (
    <div className="panel">
      <div className="panel-head">
        <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
          <h2 style={{ margin: 0, fontSize: 18, fontWeight: 700 }}>Memories</h2>
          <div className="field" style={{ margin: 0 }}>
            <select value={selectedPersonId ?? ''} onChange={e => onSelectPerson(e.target.value ? Number(e.target.value) : null)}>
              <option value="">All people</option>
              {persons.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </div>
        </div>
      </div>

      {error && <div className="notice error" onClick={clearMessages}>{error}</div>}
      {notice && <div className="notice" onClick={clearMessages}>{notice}</div>}

      <div className="row wrap" style={{ gap: 6, marginBottom: 10 }}>
        <div className="field" style={{ flex: 1, minWidth: 140 }}>
          <input
            type="text"
            placeholder="Search memories..."
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && fetchMemories()}
          />
        </div>
        <div className="field" style={{ margin: 0 }}>
          <select value={filterType} onChange={e => setFilterType(e.target.value)}>
            <option value="">All types</option>
            {MEMORY_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
          </select>
        </div>
        <div className="field" style={{ margin: 0 }}>
          <select value={filterStatus} onChange={e => setFilterStatus(e.target.value)}>
            {STATUS_OPTIONS.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
          </select>
        </div>
      </div>

      {selectedPersonId && (
        <div className="add-memory row wrap" style={{ gap: 6, marginBottom: 10 }}>
          <div className="field" style={{ flex: 1, minWidth: 140, margin: 0 }}>
            <input
              type="text"
              placeholder="Add a new memory..."
              value={newContent}
              onChange={e => setNewContent(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleAdd()}
            />
          </div>
          <div className="field" style={{ margin: 0 }}>
            <select value={newType} onChange={e => setNewType(e.target.value as MemoryType)}>
              {MEMORY_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
          <button className="ghost" onClick={handleAdd} disabled={!newContent.trim()}>Add</button>
        </div>
      )}

      {loading && <div className="muted" style={{ padding: 12 }}>Loading...</div>}

      {!loading && memories.length === 0 && (
        <div className="muted" style={{ padding: 16, textAlign: 'center' }}>
          No memories found.
        </div>
      )}

      <div className="memory-list">
        {memories.map(m => (
          <div key={m.id} className="memory-card">
            <div className="memory-top">
              <span className={chipClass(m.memory_type)}>{m.memory_type}</span>
              <span className={statusClass(m.status)}>{m.status}</span>
              <span className="muted" style={{ fontSize: 12 }}>{personName(m.person_id)}</span>
              <span className="muted" style={{ fontSize: 11, marginLeft: 'auto' }}>#{m.id}</span>
            </div>

            {editingId === m.id ? (
              <div className="memory-content">
                <textarea
                  ref={editRef}
                  className="field"
                  rows={3}
                  value={editContent}
                  onChange={e => setEditContent(e.target.value)}
                  style={{ width: '100%', boxSizing: 'border-box', resize: 'vertical' }}
                />
                <div className="row" style={{ gap: 6, marginTop: 6 }}>
                  <button className="ghost" onClick={() => handleSaveEdit(m.id)}>Save</button>
                  <button className="ghost" onClick={() => { setEditingId(null); setEditContent('') }}>Cancel</button>
                </div>
              </div>
            ) : correctingId === m.id ? (
              <div className="memory-content">
                <textarea
                  ref={correctRef}
                  className="field"
                  rows={3}
                  value={correctContent}
                  onChange={e => setCorrectContent(e.target.value)}
                  placeholder="Corrected content..."
                  style={{ width: '100%', boxSizing: 'border-box', resize: 'vertical' }}
                />
                <div className="row" style={{ gap: 6, marginTop: 6 }}>
                  <button className="ghost" onClick={() => handleSaveCorrect(m.id)}>Save Correction</button>
                  <button className="ghost" onClick={() => { setCorrectingId(null); setCorrectContent('') }}>Cancel</button>
                </div>
              </div>
            ) : (
              <div className="memory-content">{m.content}</div>
            )}

            <div className="memory-source-meta row wrap" style={{ gap: 8, fontSize: 12, marginTop: 6 }}>
              <span className="muted">Confidence: {Math.round(m.confidence * 100)}%</span>
              <span className="muted">Importance: {Math.round(m.importance * 100)}%</span>
              <span className="muted">Created: {formatShortDate(m.created_at)}</span>
              <span className="muted">Updated: {formatShortDate(m.updated_at)}</span>
            </div>

            {m.source_message_id && (
              <div style={{ marginTop: 6 }}>
                <button
                  className="ghost"
                  style={{ fontSize: 12, padding: '2px 8px' }}
                  onClick={() => toggleSource(m.source_message_id!)}
                >
                  {expandedSource.has(m.source_message_id) ? 'Hide source' : `Source message #${m.source_message_id}`}
                </button>
                {expandedSource.has(m.source_message_id) && (
                  <div className="source-card">
                    {sourceCache[m.source_message_id] ? (
                      <>
                        <div className="muted" style={{ fontSize: 11, marginBottom: 4 }}>
                          {sourceCache[m.source_message_id].sender} &middot; {formatDate(sourceCache[m.source_message_id].timestamp)}
                        </div>
                        <div style={{ fontSize: 13 }}>
                          {sourceCache[m.source_message_id].content}
                        </div>
                      </>
                    ) : (
                      <div className="muted">Loading source message...</div>
                    )}
                  </div>
                )}
              </div>
            )}

            {m.note && <div className="muted" style={{ fontSize: 12, marginTop: 4, fontStyle: 'italic' }}>Note: {m.note}</div>}

            <div className="actions row" style={{ gap: 4, marginTop: 8 }}>
              <button
                className="ghost"
                onClick={() => { setCorrectingId(m.id); setCorrectContent(m.content) }}
                disabled={editingId === m.id || correctingId === m.id}
              >
                Correct
              </button>
              <button
                className="ghost"
                onClick={() => { setEditingId(m.id); setEditContent(m.content) }}
                disabled={editingId === m.id || correctingId === m.id}
              >
                Edit
              </button>
              <button
                className="ghost"
                onClick={() => toggleVersions(m.id)}
              >
                {expandedVersions.has(m.id) ? 'Hide history' : 'History'}
              </button>
              <button
                className="ghost danger"
                onClick={() => handleDelete(m.id)}
                disabled={editingId === m.id || correctingId === m.id}
              >
                Delete
              </button>
            </div>

            {expandedVersions.has(m.id) && (
              <div className="versions">
                <div className="muted" style={{ fontSize: 12, marginBottom: 6, fontWeight: 600 }}>Version History</div>
                {!versionCache[m.id] ? (
                  <div className="muted" style={{ fontSize: 12 }}>Loading...</div>
                ) : versionCache[m.id].length === 0 ? (
                  <div className="muted" style={{ fontSize: 12 }}>No history available.</div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                    {versionCache[m.id].map(v => (
                      <div key={v.id} className="source-card" style={{ borderLeft: `3px solid ${v.status === 'active' ? '#4caf50' : '#ff9800'}` }}>
                        <div className="row wrap" style={{ gap: 6, fontSize: 11, marginBottom: 4 }}>
                          <span className="muted">Rev {v.revision}</span>
                          <span className={statusClass(v.status)}>{v.status}</span>
                          <span className="muted">{v.memory_type}</span>
                          <span className="muted">by {v.actor}</span>
                          <span className="muted" style={{ marginLeft: 'auto' }}>{formatDate(v.created_at)}</span>
                        </div>
                        <div style={{ fontSize: 12 }}>{v.content}</div>
                        {v.note && <div className="muted" style={{ fontSize: 11, marginTop: 2, fontStyle: 'italic' }}>Note: {v.note}</div>}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
