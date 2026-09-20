import type { Project } from '../../types'

type Props = {
  project: Project
  isActive: boolean
  onClick: () => void
}

export function ProjectCard({ project, isActive, onClick }: Props) {
  const stats = project.stats || {}
  const total = Object.values(stats).reduce((a, b) => a + b, 0)

  return (
    <button className={`card${isActive ? ' active' : ''}`} onClick={onClick} style={{ textAlign: 'left', width: '100%' }}>
      <strong style={{ fontSize: '0.9rem', display: 'block' }}>{project.name}</strong>
      <span className="muted" style={{ fontSize: '0.75rem' }}>
        {total.toLocaleString()} items &middot; {Object.keys(stats).length} types
      </span>
    </button>
  )
}
