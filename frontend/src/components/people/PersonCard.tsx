import { Avatar } from '../ui/Avatar'
import type { Person } from '../../types'

type Props = {
  person: Person
  isSelected: boolean
  onClick: () => void
}

export function PersonCard({ person, isSelected, onClick }: Props) {
  return (
    <button className={`person-card${isSelected ? ' active' : ''}`} onClick={onClick}>
      <span className="row" style={{ gap: 10 }}>
        <Avatar name={person.name} size="md" />
        <span>
          <strong style={{ display: 'block', fontSize: '0.9rem' }}>{person.name}</strong>
          <span className="muted" style={{ fontSize: '0.75rem' }}>{person.relationship}</span>
        </span>
      </span>
      <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: 4 }}>
        {person.message_count.toLocaleString()} messages
      </span>
    </button>
  )
}
