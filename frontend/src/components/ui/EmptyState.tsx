type Props = {
  title: string
  description?: string
  action?: { label: string; onClick: () => void }
}

export function EmptyState({ title, description, action }: Props) {
  return (
    <div className="empty-state">
      <div style={{ fontSize: '1.4rem', marginBottom: 8, opacity: 0.4 }}>
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="10" />
          <path d="M12 16v-4" />
          <path d="M12 8h.01" />
        </svg>
      </div>
      <div style={{ fontWeight: 600, marginBottom: 4 }}>{title}</div>
      {description && (
        <div style={{ fontSize: '0.85rem', maxWidth: 360, lineHeight: 1.5 }}>
          {description}
        </div>
      )}
      {action && (
        <button
          type="button"
          className="btn btn-ghost"
          style={{ marginTop: 16 }}
          onClick={action.onClick}
        >
          {action.label}
        </button>
      )}
    </div>
  )
}
