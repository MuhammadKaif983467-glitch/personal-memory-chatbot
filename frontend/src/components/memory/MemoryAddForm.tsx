import { useState } from 'react'
import type { Memory } from '../../types'

type MemoryType = Memory['memory_type']
const MEMORY_TYPES: MemoryType[] = ['FACT', 'PREFERENCE', 'INTEREST', 'RELATIONSHIP', 'EVENT', 'HABIT', 'OPINION', 'CONVERSATION', 'TEMPORARY']

interface Props {
  onAdd: (content: string, type: MemoryType) => void
}

export default function MemoryAddForm({ onAdd }: Props) {
  const [content, setContent] = useState('')
  const [type, setType] = useState<MemoryType>('FACT')

  const handleSubmit = () => {
    if (!content.trim()) return
    onAdd(content.trim(), type)
    setContent('')
  }

  return (
    <div className="card" style={{ marginBottom: 16 }}>
      <div className="row" style={{ gap: 8 }}>
        <input className="input" style={{ flex: 1 }} type="text" placeholder="Add a new memory..." value={content} onChange={e => setContent(e.target.value)} onKeyDown={e => e.key === 'Enter' && handleSubmit()} />
        <select className="input" style={{ width: 'auto', padding: '8px 12px' }} value={type} onChange={e => setType(e.target.value as MemoryType)}>
          {MEMORY_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
        </select>
        <button className="btn btn-primary" onClick={handleSubmit} disabled={!content.trim()}>Add</button>
      </div>
    </div>
  )
}
