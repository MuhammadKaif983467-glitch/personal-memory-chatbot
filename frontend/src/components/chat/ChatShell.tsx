import { useState, useRef, useEffect, useCallback } from 'react'
import type { Person, Conversation, MessageRecord, ChatTurn, ChatResponse, PaginatedMessages } from '../../types'
import { api } from '../../services/api'
import { ConversationRail } from './ConversationRail'
import { ConversationHeader } from './ConversationHeader'
import { MessageList } from './MessageList'

type Props = {
  persons: Person[]
  selectedPersonId: number | null
  onSelectPerson: (id: number | null) => void
  selectedProjectId: number | null
  showMemorySources: boolean
  debugRetrieval: boolean
}

const PAGE_SIZE = 200

export function ChatShell({
  persons,
  selectedPersonId,
  onSelectPerson,
  selectedProjectId,
  showMemorySources,
  debugRetrieval,
}: Props) {
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [activeConversationId, setActiveConversationId] = useState<number | null>(null)
  const [turns, setTurns] = useState<ChatTurn[]>([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [deletingId, setDeletingId] = useState<number | null>(null)
  const [totalMessages, setTotalMessages] = useState(0)
  const [messageOffset, setMessageOffset] = useState(0)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<MessageRecord[]>([])
  const [searching, setSearching] = useState(false)

  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const epochRef = useRef(0)

  const person = persons.find((p) => p.id === selectedPersonId) ?? null

  const loadConversations = useCallback(async (signal?: AbortSignal) => {
    try {
      const data = await api.listConversations(selectedProjectId, signal)
      setConversations(data)
      setError(null)
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === 'AbortError') return
      const msg = err instanceof Error ? err.message : 'Failed to load conversations'
      setError(`Conversations: ${msg}`)
    }
  }, [selectedProjectId])

  useEffect(() => {
    const controller = new AbortController()
    void loadConversations(controller.signal)
    return () => controller.abort()
  }, [loadConversations])

  useEffect(() => {
    if (conversations.length === 0 && !error) {
      const timer = setTimeout(loadConversations, 3000)
      return () => clearTimeout(timer)
    }
  }, [conversations.length, error, loadConversations])

  useEffect(() => {
    if (activeConversationId === null) {
      setTurns([])
      setTotalMessages(0)
      setMessageOffset(0)
      return
    }
    let cancelled = false
    setMessageOffset(0)
    ;(async () => {
      try {
        const result: PaginatedMessages = await api.listMessages({
          conversationId: activeConversationId,
          limit: PAGE_SIZE,
          offset: 0,
        })
        if (cancelled) return
        setTotalMessages(result.total)
        setMessageOffset(result.items.length)
        const mapped: ChatTurn[] = result.items.map((m) => {
          const isMe = person != null && m.sender === person.name
          return {
            id: m.id,
            role: isMe ? 'user' : 'assistant',
            content: m.content,
            at: m.timestamp ? new Date(m.timestamp).getTime() : undefined,
            speakerName: isMe ? 'You' : m.sender,
          }
        })
        setTurns(mapped)
      } catch (err: unknown) {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Failed to load messages')
      }
    })()
    return () => { cancelled = true }
  }, [activeConversationId, person])

  const loadMoreMessages = useCallback(async () => {
    if (!activeConversationId || messageOffset >= totalMessages) return
    try {
      const result: PaginatedMessages = await api.listMessages({
        conversationId: activeConversationId,
        limit: PAGE_SIZE,
        offset: messageOffset,
      })
      setTotalMessages(result.total)
      setMessageOffset((prev) => prev + result.items.length)
      const mapped: ChatTurn[] = result.items.map((m) => {
        const isMe = person != null && m.sender === person.name
        return {
          id: m.id,
          role: isMe ? 'user' : 'assistant',
          content: m.content,
          at: m.timestamp ? new Date(m.timestamp).getTime() : undefined,
          speakerName: isMe ? 'You' : m.sender,
        }
      })
      setTurns((prev) => [...prev, ...mapped])
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load more messages')
    }
  }, [activeConversationId, messageOffset, totalMessages, person])

  const handleSearch = useCallback(async () => {
    if (!searchQuery.trim() || !activeConversationId) {
      setSearchResults([])
      return
    }
    setSearching(true)
    try {
      const results = await api.searchMessages({
        query: searchQuery,
        conversationId: activeConversationId,
      })
      setSearchResults(results)
    } catch {
      setSearchResults([])
    } finally {
      setSearching(false)
    }
  }, [searchQuery, activeConversationId])

  useEffect(() => {
    epochRef.current += 1
    setActiveConversationId(null)
    setTurns([])
    setInput('')
    setError(null)
    setNotice(null)
    setDeletingId(null)
    setTotalMessages(0)
    setMessageOffset(0)
    setSearchQuery('')
    setSearchResults([])
  }, [selectedPersonId, selectedProjectId])

  const handleSend = useCallback(async () => {
    const text = input.trim()
    if (!text || sending) return
    if (!selectedPersonId) {
      setError('Select a person first')
      return
    }

    const myEpoch = epochRef.current
    setSending(true)
    setError(null)
    setNotice(null)
    setInput('')

    const userTurn: ChatTurn = {
      id: Date.now(),
      role: 'user',
      content: text,
      at: Date.now(),
      speakerName: 'You',
    }
    setTurns((prev) => [...prev, userTurn])

    try {
      const resp: ChatResponse = await api.chat({
        message: text,
        person_id: selectedPersonId,
        conversation_id: activeConversationId ?? undefined,
        debug: debugRetrieval,
      })

      if (epochRef.current !== myEpoch) return

      if (!activeConversationId && resp.conversation_id) {
        setActiveConversationId(resp.conversation_id)
        loadConversations()
      }

      const assistantTurn: ChatTurn = {
        id: Date.now() + 1,
        role: 'assistant',
        content: resp.reply,
        at: Date.now(),
        confidence: resp.confidence,
        sources: resp.show_memory_sources ? resp.sources : undefined,
        learned: resp.learned,
        debug: resp.debug,
        memoryIndicator: resp.memory_indicator,
        speakerName: person?.name ?? 'Assistant',
      }
      setTurns((prev) => [...prev, assistantTurn])
    } catch (err: unknown) {
      if (epochRef.current !== myEpoch) return
      setError(err instanceof Error ? err.message : 'Failed to get response')
      setTurns((prev) => prev.filter((t) => t.id !== userTurn.id))
      setInput(text)
    } finally {
      if (epochRef.current === myEpoch) setSending(false)
    }
  }, [input, sending, selectedPersonId, activeConversationId, debugRetrieval, loadConversations, person])

  const handleDelete = useCallback(
    async (id: number) => {
      if (deletingId !== null) return
      setDeletingId(id)
      try {
        await api.deleteConversation(id)
        setConversations((prev) => prev.filter((c) => c.id !== id))
        if (activeConversationId === id) {
          setActiveConversationId(null)
          setTurns([])
        }
        setNotice('Conversation deleted')
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : 'Failed to delete conversation')
      } finally {
        setDeletingId(null)
      }
    },
    [deletingId, activeConversationId],
  )

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault()
        handleSend()
      }
    },
    [handleSend],
  )

  const handleNewConversation = useCallback(() => {
    setActiveConversationId(null)
    setTurns([])
  }, [])

  const handleSelectConversation = useCallback((id: number) => {
    setActiveConversationId(id)
    setTurns([])
  }, [])

  const autoGrow = useCallback(() => {
    const ta = textareaRef.current
    if (!ta) return
    ta.style.height = '42px'
    ta.style.height = Math.min(ta.scrollHeight, 160) + 'px'
  }, [])

  useEffect(() => { autoGrow() }, [input, autoGrow])

  const sortedConversations = [...conversations].sort(
    (a, b) => new Date(b.started_at ?? 0).getTime() - new Date(a.started_at ?? 0).getTime(),
  )

  const providerAvailable = selectedPersonId !== null || activeConversationId !== null

  return (
    <div className="chat-layout">
      <ConversationRail
        conversations={sortedConversations}
        activeConversationId={activeConversationId}
        onSelect={handleSelectConversation}
        onDelete={handleDelete}
        deletingId={deletingId}
        personName={person?.name ?? ''}
        onNew={handleNewConversation}
      />

      <main className="chat-window">
        <ConversationHeader
          person={person}
          persons={persons}
          selectedPersonId={selectedPersonId}
          onSelectPerson={onSelectPerson}
          conversationId={activeConversationId}
          projectId={selectedProjectId}
        />

        {error && <div className="error" onClick={() => setError(null)}>{error}</div>}
        {notice && <div className="notice" onClick={() => setNotice(null)}>{notice}</div>}

        {activeConversationId && totalMessages > PAGE_SIZE && (
          <div style={{ padding: '4px 12px', display: 'flex', gap: 6, alignItems: 'center' }}>
            <input
              type="text"
              className="input"
              style={{ flex: 1, padding: '4px 8px', fontSize: '0.75rem' }}
              placeholder="Search in conversation..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') handleSearch() }}
            />
            <button className="btn btn-ghost" style={{ padding: '4px 8px', fontSize: '0.75rem' }} onClick={handleSearch}>
              {searching ? '...' : 'Search'}
            </button>
            {searchResults.length > 0 && (
              <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>{searchResults.length} results</span>
            )}
          </div>
        )}

        <MessageList
          turns={turns}
          sending={sending}
          personName={person?.name ?? ''}
          showMemorySources={showMemorySources}
          selectedPersonId={selectedPersonId}
          activeConversationId={activeConversationId}
        />

        {activeConversationId && messageOffset < totalMessages && (
          <div style={{ padding: '8px', textAlign: 'center' }}>
            <button className="btn btn-ghost" style={{ fontSize: '0.75rem' }} onClick={loadMoreMessages}>
              Load older messages ({messageOffset} of {totalMessages})
            </button>
          </div>
        )}

        <div className="composer">
          <div className="composer-inner">
            <textarea
              ref={textareaRef}
              rows={1}
              className="composer-textarea"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              aria-label={`Message ${person?.name ?? ''}`}
              placeholder={
                providerAvailable
                  ? `Message ${person?.name ?? ''}...`
                  : 'Select a person to start...'
              }
              disabled={!providerAvailable}
            />
            <button
              className="composer-send"
              disabled={!input.trim() || sending || !providerAvailable}
              onClick={handleSend}
              aria-label="Send message"
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="22" y1="2" x2="11" y2="13" />
                <polygon points="22 2 15 22 11 13 2 9 22 2" />
              </svg>
            </button>
          </div>
        </div>
      </main>
    </div>
  )
}
