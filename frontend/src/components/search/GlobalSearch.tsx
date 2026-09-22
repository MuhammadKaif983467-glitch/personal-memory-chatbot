import { useState, useCallback, useRef, useEffect } from 'react'
import type { SearchResponse } from '../../types'
import { api, errText } from '../../services/api'

type Props = {
  open: boolean
  onClose: () => void
  projectId?: number | null
  onSelectConversation?: (id: number) => void
  onSelectPerson?: (id: number) => void
}

export function GlobalSearch({ open, onClose, projectId, onSelectConversation, onSelectPerson }: Props) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<SearchResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const debounceRef = useRef<ReturnType<typeof setTimeout>>()

  useEffect(() => {
    if (open) {
      setQuery('')
      setResults(null)
      setError(null)
      setTimeout(() => inputRef.current?.focus(), 50)
    }
  }, [open])

  const doSearch = useCallback(async (q: string) => {
    if (!q.trim()) { setResults(null); return }
    setLoading(true); setError(null)
    try {
      const res = await api.search({ query: q.trim(), project_id: projectId ?? undefined, limit: 20 })
      setResults(res)
    } catch (err) { setError(errText(err)) }
    finally { setLoading(false) }
  }, [projectId])

  const handleChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const v = e.target.value
    setQuery(v)
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => void doSearch(v), 250)
  }, [doSearch])

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Escape') onClose()
  }, [onClose])

  const handleSelect = useCallback((type: string, id: number) => {
    if (type === 'conversation') onSelectConversation?.(id)
    else if (type === 'person') onSelectPerson?.(id)
    onClose()
  }, [onClose, onSelectConversation, onSelectPerson])

  if (!open) return null

  return (
    <div className="modal-overlay" onClick={onClose} role="dialog" aria-modal="true" aria-label="Search">
      <div className="global-search" onClick={(e) => e.stopPropagation()}>
        <input
          ref={inputRef}
          type="text"
          className="input"
          style={{ width: '100%', padding: '12px 16px', fontSize: '1rem', boxSizing: 'border-box' }}
          placeholder="Search messages, memories, conversations... (Esc to close)"
          value={query}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
        />
        {error && <div className="error" style={{ margin: '8px 16px' }} onClick={() => setError(null)}>{error}</div>}
        {loading && <div style={{ padding: '12px 16px', color: 'var(--text-muted)', fontSize: '0.85rem' }}>Searching...</div>}
        {results && !loading && (
          <div style={{ maxHeight: 400, overflowY: 'auto', padding: '8px 0' }}>
            {results.messages.length === 0 && results.memories.length === 0 && results.conversations.length === 0 && (
              <div style={{ padding: '12px 16px', color: 'var(--text-muted)' }}>No results</div>
            )}
            {results.conversations.length > 0 && (
              <div style={{ padding: '4px 16px', fontSize: '0.7rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase' }}>Conversations</div>
            )}
            {results.conversations.map((c) => (
              <button key={c.conversation_id} type="button" className="search-result-item"
                style={{ display: 'block', width: '100%', textAlign: 'left', padding: '8px 16px', background: 'none', border: 'none', cursor: 'pointer' }}
                onClick={() => handleSelect('conversation', c.conversation_id)}>
                <div style={{ fontSize: '0.85rem' }}>{c.title || `Conversation ${c.conversation_id}`}</div>
                <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>{c.message_count} messages</div>
              </button>
            ))}
            {results.messages.length > 0 && (
              <div style={{ padding: '4px 16px', fontSize: '0.7rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase' }}>Messages</div>
            )}
            {results.messages.map((m) => (
              <div key={m.message_id} style={{ padding: '6px 16px', fontSize: '0.85rem', cursor: 'default' }}>
                <span style={{ color: 'var(--text-muted)', fontSize: '0.7rem' }}>{m.sender}</span>
                <span style={{ margin: '0 4px', color: 'var(--text-muted)' }}>&middot;</span>
                <span>{m.content.slice(0, 80)}{m.content.length > 80 ? '...' : ''}</span>
              </div>
            ))}
            {results.memories.length > 0 && (
              <div style={{ padding: '4px 16px', fontSize: '0.7rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase' }}>Memories</div>
            )}
            {results.memories.map((m) => (
              <div key={m.memory_id} style={{ padding: '6px 16px', fontSize: '0.85rem', cursor: 'default' }}>
                <span style={{ fontSize: '0.7rem', color: 'var(--accent)' }}>{m.memory_type}</span>
                <span style={{ margin: '0 4px', color: 'var(--text-muted)' }}>&middot;</span>
                <span style={{ color: 'var(--text-muted)', fontSize: '0.7rem' }}>{m.person_name}</span>
                <span style={{ margin: '0 4px', color: 'var(--text-muted)' }}>&middot;</span>
                <span>{m.content.slice(0, 80)}{m.content.length > 80 ? '...' : ''}</span>
              </div>
            ))}
            <div style={{ padding: '6px 16px', fontSize: '0.7rem', color: 'var(--text-muted)' }}>
              {results.total} total results
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
