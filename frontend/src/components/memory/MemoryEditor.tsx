import { useRef, useEffect } from 'react'

interface Props {
  content: string
  onChange: (value: string) => void
  onSave: () => void
  onCancel: () => void
  placeholder?: string
}

export default function MemoryEditor({ content, onChange, onSave, onCancel, placeholder }: Props) {
  const ref = useRef<HTMLTextAreaElement | null>(null)

  useEffect(() => {
    if (ref.current) { ref.current.focus(); ref.current.select() }
  }, [])

  return (
    <div>
      <textarea
        ref={ref}
        className="textarea"
        rows={3}
        value={content}
        onChange={e => onChange(e.target.value)}
        onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); onSave() } if (e.key === 'Escape') onCancel() }}
        placeholder={placeholder}
        style={{ width: '100%', resize: 'vertical', marginBottom: 8 }}
      />
      <div className="row" style={{ gap: 6 }}>
        <button className="btn btn-primary" onClick={onSave} style={{ padding: '4px 12px', fontSize: '0.8rem' }}>Save</button>
        <button className="btn btn-ghost" onClick={onCancel} style={{ padding: '4px 12px', fontSize: '0.8rem' }}>Cancel</button>
      </div>
    </div>
  )
}
