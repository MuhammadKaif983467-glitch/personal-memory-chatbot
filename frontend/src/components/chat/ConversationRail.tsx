import type { Conversation } from '../../types'

type Props = {
  conversations: Conversation[]
  activeConversationId: number | null
  onSelect: (id: number) => void
  onDelete: (id: number) => void
  deletingId: number | null
  personName: string
  onNew: () => void
}

export function ConversationRail({
  conversations,
  activeConversationId,
  onSelect,
  onDelete,
  deletingId,
  personName,
  onNew,
}: Props) {
  return (
    <aside className="conversation-rail" aria-label="Conversations">
      <div className="rail-head">
        <span>Conversations</span>
        <button className="icon-btn" onClick={onNew} title="New conversation" aria-label="New conversation">
          +
        </button>
      </div>
      <div className="rail-summary" aria-live="polite">
        {conversations.length} conversations
      </div>
      <div className="conversation-list" role="listbox" aria-label="Conversation list">
        {activeConversationId === null && personName && (
          <div className="conv-row active-row" role="option" aria-selected="true">
            <button className="conv-row-btn" onClick={onNew}>
              <div className="conv-title">New conversation</div>
            </button>
          </div>
        )}
        {conversations.map((c) => (
          <div
            key={c.id}
            className={`conv-row${c.id === activeConversationId ? ' active-row' : ''}`}
            role="option"
            aria-selected={c.id === activeConversationId}
          >
            <button
              className="conv-row-btn"
              onClick={() => onSelect(c.id)}
            >
              <div className="conv-title">{c.title || `Conversation ${c.id}`}</div>
              <div className="conv-meta">
                <span>{c.message_count} msgs</span>
                <span>
                  {c.started_at ? new Date(c.started_at).toLocaleDateString() : '—'}
                </span>
              </div>
            </button>
            <button
              className="conv-delete"
              title="Delete"
              aria-label={`Delete conversation ${c.title || c.id}`}
              disabled={deletingId === c.id}
              onClick={(e) => { e.stopPropagation(); onDelete(c.id) }}
            >
              ×
            </button>
          </div>
        ))}
        {conversations.length === 0 && personName && (
          <div className="conv-empty">No conversations yet</div>
        )}
      </div>
    </aside>
  )
}
