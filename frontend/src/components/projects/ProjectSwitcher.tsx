import type { Project } from '../../types'

type Props = {
  projects: Project[]
  activeId: number | null
  onSelect: (id: number) => void
  onNew: () => void
}

export function ProjectSwitcher({ projects, activeId, onSelect, onNew }: Props) {
  return (
    <div className="row" style={{ gap: 8, alignItems: 'center' }}>
      <select
        className="input"
        style={{ flex: 1, padding: '8px 12px' }}
        value={activeId ?? ''}
        onChange={(e) => {
          const v = Number(e.target.value)
          if (v) onSelect(v)
        }}
      >
        <option value="">No project selected</option>
        {projects.map((p) => (
          <option key={p.id} value={p.id}>{p.name}</option>
        ))}
      </select>
      <button className="btn btn-ghost" onClick={onNew}>
        + New
      </button>
    </div>
  )
}
