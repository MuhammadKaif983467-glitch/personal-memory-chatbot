import type { Person } from '../../types'
import { Avatar } from '../ui/Avatar'
import { SummaryButton } from './SummaryButton'

type Props = {
  person: Person | null
  persons: Person[]
  selectedPersonId: number | null
  onSelectPerson: (id: number | null) => void
  conversationId?: number | null
  projectId?: number | null
}

function isCombinedName(name: string): boolean {
  return name.includes(',')
}

export function ConversationHeader({
  person,
  persons,
  selectedPersonId,
  onSelectPerson,
  conversationId,
  projectId,
}: Props) {
  const filteredPersons = persons.filter((p) => !isCombinedName(p.name))

  return (
    <div className="panel-head">
      <div className="head-title">
        {person ? (
          <span className="row">
            <Avatar name={person.name} size="sm" />
            {person.name}
          </span>
        ) : (
          'Select a person'
        )}
      </div>
      <div className="head-sub" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <select
          value={selectedPersonId ?? ''}
          onChange={(e) => {
            const v = e.target.value
            onSelectPerson(v ? Number(v) : null)
          }}
        >
          <option value="">Select person...</option>
          {filteredPersons.map((p) => (
            <option key={p.id} value={p.id}>{p.name}</option>
          ))}
        </select>
        <SummaryButton conversationId={conversationId ?? null} projectId={projectId} />
      </div>
    </div>
  )
}
