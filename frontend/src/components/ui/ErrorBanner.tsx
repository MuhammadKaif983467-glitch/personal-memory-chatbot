import { useState } from 'react'

type Props = {
  message: string
  onDismiss?: () => void
  details?: string
}

export function ErrorBanner({ message, onDismiss, details }: Props) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="error" onClick={() => (onDismiss ? onDismiss() : setExpanded(!expanded))}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span>{message}</span>
        {onDismiss && (
          <button
            type="button"
            className="icon-btn"
            style={{ width: 20, height: 20, fontSize: '0.75rem' }}
            onClick={(e) => {
              e.stopPropagation()
              onDismiss()
            }}
          >
            x
          </button>
        )}
      </div>
      {details && expanded && (
        <div style={{ marginTop: 8, fontSize: '0.75rem', opacity: 0.8, lineHeight: 1.5 }}>
          {details}
        </div>
      )}
    </div>
  )
}
