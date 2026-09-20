import { useState, useEffect, useCallback } from 'react'
import type { Memory, MemoryVersion, MessageRecord, Person } from '../../types'
import { api } from '../../services/api'
import MemoryToolbar from './MemoryToolbar'
import MemoryFilters from './MemoryFilters'
import MemoryCard from './MemoryCard'
import MemoryAddForm from './MemoryAddForm'
import MemoryEmptyState from './MemoryEmptyState'

interface Props {
  persons: Person[]
  selectedPersonId: number | null
  onSelectPerson: (id: number | null) => void
}

export default function MemoryShell({ persons, selectedPersonId, onSelectPerson }: Props) {
  const [memories, setMemories] = useState<Memory[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [filterType, setFilterType] = useState('')
  const [filterStatus, setFilterStatus] = useState('active')
  const [editingId, setEditingId] = useState<number | null>(null)
  const [editContent, setEditContent] = useState('')
  const [correctingId, setCorrectingId] = useState<number | null>(null)
  const [correctContent, setCorrectContent] = useState('')
  const [expandedVersions, setExpandedVersions] = useState<Set<number>>(new Set())
  const [versionCache, setVersionCache] = useState<Record<number, MemoryVersion[]>>({})
  const [sourceCache, setSourceCache] = useState<Record<number, MessageRecord>>({})
  const [expandedSource, setExpandedSource] = useState<Set<number>>(new Set())
  const [showFilters, setShowFilters] = useState(false)

  const flash = (msg: string) => { setNotice(msg); setTimeout(() => setNotice(null), 4000) }
  const err = (e: any, fallback: string) => setError(e?.message ?? fallback)

  const fetchMemories = useCallback(async () => {
    setLoading(true); setError(null)
    try {
      const p: Record<string, unknown> = { status: filterStatus }
      if (selectedPersonId) p.personId = selectedPersonId
      if (filterType) p.memoryType = filterType
      if (searchQuery.trim()) p.queryText = searchQuery.trim()
      setMemories((await api.listMemories(p)) ?? [])
    } catch (e: any) { err(e, 'Failed to load memories') }
    finally { setLoading(false) }
  }, [selectedPersonId, filterType, filterStatus, searchQuery])

  useEffect(() => { fetchMemories() }, [fetchMemories])

  const handleAdd = async (content: string, type: Memory['memory_type']) => {
    if (!selectedPersonId) return; setError(null); setNotice(null)
    try { await api.createMemory({ person_id: selectedPersonId, content, memory_type: type }); flash('Memory added'); fetchMemories() }
    catch (e: any) { err(e, 'Failed to add memory') }
  }

  const handleSaveEdit = async (id: number) => {
    setError(null); setNotice(null)
    try { await api.editMemory(id, editContent.trim()); setEditingId(null); setEditContent(''); flash('Memory updated'); fetchMemories() }
    catch (e: any) { err(e, 'Failed to update') }
  }

  const handleSaveCorrect = async (id: number) => {
    setError(null); setNotice(null)
    try { await api.correctMemory(id, correctContent.trim()); setCorrectingId(null); setCorrectContent(''); flash('Memory corrected'); fetchMemories() }
    catch (e: any) { err(e, 'Failed to correct') }
  }

  const handleDelete = async (id: number) => {
    if (!confirm('Delete this memory permanently?')) return; setError(null); setNotice(null)
    try { await api.deleteMemory(id); flash('Memory deleted'); fetchMemories() }
    catch (e: any) { err(e, 'Failed to delete') }
  }

  const toggleVersions = async (id: number) => {
    const next = new Set(expandedVersions)
    if (next.has(id)) { next.delete(id); setExpandedVersions(next); return }
    next.add(id); setExpandedVersions(next)
    if (!versionCache[id]) {
      try {
        const versions = await api.getMemoryVersions(id)
        setVersionCache(p => ({ ...p, [id]: versions ?? [] }))
      } catch (e: any) { err(e, 'Failed to load history') }
    }
  }

  const toggleSource = async (msgId: number) => {
    const next = new Set(expandedSource)
    if (next.has(msgId)) { next.delete(msgId); setExpandedSource(next); return }
    next.add(msgId); setExpandedSource(next)
    if (!sourceCache[msgId]) {
      try {
        const message = await api.getMessage(msgId)
        setSourceCache(p => ({ ...p, [msgId]: message }))
      } catch (e: any) { err(e, 'Failed to load source message') }
    }
  }

  const personName = (id: number) => persons.find(p => p.id === id)?.name ?? `Person #${id}`
  const hasActiveFilters = !!(filterType || filterStatus !== 'active' || searchQuery)

  return (
    <div className="panel">
      <header className="panel-head" style={{ background: 'transparent', borderBottom: '1px solid var(--border-subtle)' }}>
        <div className="row-between">
          <div>
            <h2 style={{ fontSize: '1.1rem', fontWeight: 700, margin: 0 }}>Memories</h2>
            <p className="muted" style={{ fontSize: '0.85rem', marginTop: 4 }}>Everything remembered about the people in your life</p>
          </div>
          <select className="input" style={{ width: 'auto', padding: '6px 10px', fontSize: '0.8rem' }} value={selectedPersonId ?? ''} onChange={e => onSelectPerson(e.target.value ? Number(e.target.value) : null)}>
            <option value="">All people</option>
            {persons.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
        </div>
      </header>
      {error && <div className="error" onClick={() => { setError(null); setNotice(null) }}>{error}</div>}
      {notice && <div className="notice status-ok" onClick={() => { setError(null); setNotice(null) }}>{notice}</div>}
      <MemoryToolbar searchQuery={searchQuery} onSearchChange={setSearchQuery} onSearch={fetchMemories} showFilters={showFilters} onToggleFilters={() => setShowFilters(f => !f)} hasActiveFilters={hasActiveFilters} onClearFilters={() => { setFilterType(''); setFilterStatus('active'); setSearchQuery('') }} />
      {showFilters && <MemoryFilters filterType={filterType} filterStatus={filterStatus} onFilterTypeChange={setFilterType} onFilterStatusChange={setFilterStatus} />}
      {selectedPersonId && <MemoryAddForm onAdd={handleAdd} />}
      {loading && <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>{[1, 2, 3].map(i => <div key={i} className="skeleton skeleton-bubble" />)}</div>}
      {!loading && memories.length === 0 && <MemoryEmptyState />}
      <div className="memory-list">
        {memories.map(m => (
          <MemoryCard key={m.id} memory={m} editingId={editingId} correctingId={correctingId} editContent={editContent} correctContent={correctContent} expandedVersions={expandedVersions} versionCache={versionCache} expandedSource={expandedSource} sourceCache={sourceCache} onEditContentChange={setEditContent} onCorrectContentChange={setCorrectContent} onSaveEdit={handleSaveEdit} onSaveCorrect={handleSaveCorrect} onCancelEdit={() => { setEditingId(null); setEditContent('') }} onCancelCorrect={() => { setCorrectingId(null); setCorrectContent('') }} onStartEdit={(id, c) => { setEditingId(id); setEditContent(c) }} onStartCorrect={(id, c) => { setCorrectingId(id); setCorrectContent(c) }} onToggleVersions={toggleVersions} onToggleSource={toggleSource} onDelete={handleDelete} personName={personName} />
        ))}
      </div>
    </div>
  )
}
