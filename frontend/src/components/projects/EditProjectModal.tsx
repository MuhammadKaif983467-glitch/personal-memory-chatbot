import { useState, useEffect } from 'react'
import type { Project } from '../../types'
import { api } from '../../services/api'

type Props = {
  open: boolean
  project: Project | null
  onClose: () => void
  onSaved: () => void
  onDeleted: () => void
}

export function EditProjectModal({ open, project, onClose, onSaved, onDeleted }: Props) {
  const [name, setName] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [deleting, setDeleting] = useState(false)

  useEffect(() => {
    if (project) {
      setName(project.name)
      setConfirmDelete(false)
      setError(null)
    }
  }, [project])

  if (!open || !project) return null

  const handleRename = async (e: React.FormEvent) => {
    e.preventDefault()
    const trimmed = name.trim()
    if (!trimmed) { setError('Project name is required'); return }
    if (trimmed === project.name) { onClose(); return }

    setLoading(true)
    setError(null)
    try {
      await api.updateProject(project.id, { name: trimmed })
      onSaved()
      onClose()
    } catch (e: any) {
      setError(e?.message || 'Failed to rename project')
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async () => {
    if (!confirmDelete) { setConfirmDelete(true); return }
    setDeleting(true)
    setError(null)
    try {
      await api.deleteProject(project.id)
      onDeleted()
      onClose()
    } catch (e: any) {
      setError(e?.message || 'Failed to delete project')
    } finally {
      setDeleting(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 420 }}>
        <h3 style={{ marginTop: 0 }}>Edit Project</h3>
        {error && <div className="error" onClick={() => setError(null)}>{error}</div>}

        <form onSubmit={handleRename}>
          <label className="muted" style={{ display: 'block', marginBottom: 4, fontSize: '0.85rem' }}>
            Project Name
          </label>
          <input
            className="input"
            style={{ width: '100%', marginBottom: 16 }}
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Project name"
            autoFocus
          />

          <div className="row-between">
            <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn btn-ghost" disabled={loading || !name.trim()}>
              {loading ? 'Saving...' : 'Save'}
            </button>
          </div>
        </form>

        <div style={{ borderTop: '1px solid var(--border-subtle)', marginTop: 16, paddingTop: 16 }}>
          <p className="muted" style={{ fontSize: '0.8rem', marginBottom: 8 }}>Danger zone</p>
          {confirmDelete ? (
            <div>
              <p style={{ fontSize: '0.85rem', marginBottom: 8 }}>
                This will permanently delete <strong>{project.name}</strong> and all its data.
              </p>
              <div className="row" style={{ gap: 8 }}>
                <button type="button" className="btn btn-ghost" onClick={() => setConfirmDelete(false)}>
                  Cancel
                </button>
                <button
                  type="button"
                  className="btn"
                  style={{ background: 'var(--danger, #dc3545)', color: '#fff' }}
                  onClick={handleDelete}
                  disabled={deleting}
                >
                  {deleting ? 'Deleting...' : 'Confirm Delete'}
                </button>
              </div>
            </div>
          ) : (
            <button
              type="button"
              className="btn btn-ghost"
              style={{ color: 'var(--danger, #dc3545)', borderColor: 'var(--danger, #dc3545)' }}
              onClick={handleDelete}
            >
              Delete Project
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
