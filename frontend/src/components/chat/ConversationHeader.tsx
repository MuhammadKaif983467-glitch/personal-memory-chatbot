import type { Person } from '../../types'
import { Avatar } from '../ui/Avatar'

type Props = {
  person: Person | null
  persons: Person[]
  selectedPersonId: number | null
  onSelectPerson: (id: number | null) => void
}

function isCombinedName(name: string): boolean {
  return name.includes(',')
}

export function ConversationHeader({
  person,
  persons,
  selectedPersonId,
  onSelectPerson,
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
      <div className="head-sub">
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
      </div>
    </div>
  )
}
