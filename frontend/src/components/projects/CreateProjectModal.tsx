import { useState } from 'react'
import type { ProjectCreatePayload } from '../../types'
import { api } from '../../services/api'

type Props = { open: boolean; onClose: () => void; onCreated: () => void }

export function CreateProjectModal({ open, onClose, onCreated }: Props) {
  const [name, setName] = useState('')
  const [twoPerson, setTwoPerson] = useState(false)
  const [participants, setParticipants] = useState([
    { name: '', role: 'user' },
    { name: '', role: 'other' },
  ])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (!open) return null

  const updateP = (i: number, field: 'name' | 'role', val: string) => {
    setParticipants((prev) => prev.map((p, idx) => (idx === i ? { ...p, [field]: val } : p)))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) { setError('Project name is required'); return }
    const filled = participants.filter((p) => p.name.trim())
    if (filled.length === 0) { setError('Add at least one participant'); return }

    setLoading(true)
    setError(null)
    try {
      await api.createProject({ name: name.trim(), participants: filled } satisfies ProjectCreatePayload)
      onCreated()
      onClose()
      setName('')
      setParticipants([{ name: '', role: 'user' }, { name: '', role: 'other' }])
    } catch (e: any) {
      setError(e?.message || 'Failed to create project')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3 style={{ marginTop: 0 }}>Create Project</h3>
        {error && <div className="error" onClick={() => setError(null)}>{error}</div>}
        <form onSubmit={handleSubmit}>
          <label className="muted" style={{ display: 'block', marginBottom: 4, fontSize: '0.85rem' }}>Project Name</label>
          <input className="input" style={{ width: '100%', marginBottom: 16 }} value={name} onChange={(e) => setName(e.target.value)} placeholder="My project" />

          <div style={{ marginBottom: 16 }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', fontSize: '0.85rem' }}>
              <input type="checkbox" checked={twoPerson} onChange={(e) => { setTwoPerson(e.target.checked); if (e.target.checked && participants.length < 2) setParticipants([{ name: '', role: 'user' }, { name: '', role: 'other' }]) }} />
              Two-person conversation
            </label>
          </div>

          <div style={{ marginBottom: 16 }}>
            <label className="muted" style={{ display: 'block', marginBottom: 4, fontSize: '0.85rem' }}>Participants</label>
            {participants.map((p, i) => (
              <div key={i} className="row" style={{ gap: 8, marginBottom: 8 }}>
                <input className="input" style={{ flex: 1 }} placeholder="Name" value={p.name} onChange={(e) => updateP(i, 'name', e.target.value)} />
                <input className="input" style={{ width: 100 }} placeholder="Role" value={p.role} onChange={(e) => updateP(i, 'role', e.target.value)} />
                {!twoPerson && participants.length > 1 && (
                  <button type="button" className="btn btn-ghost" onClick={() => setParticipants((prev) => prev.filter((_, idx) => idx !== i))}>x</button>
                )}
              </div>
            ))}
            {!twoPerson && (
              <button type="button" className="btn btn-ghost" onClick={() => setParticipants((prev) => [...prev, { name: '', role: 'participant' }])}>+ Add participant</button>
            )}
          </div>

          <div className="row-between">
            <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn btn-ghost" disabled={loading}>{loading ? 'Creating...' : 'Create'}</button>
          </div>
        </form>
      </div>
    </div>
  )
}
