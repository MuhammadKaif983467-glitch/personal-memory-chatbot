import { PersonPanel } from '../components/PersonPanel'
import type { Person } from '../types'

type Props = {
  persons: Person[]
  selectedPersonId: number | null
  onSelectPerson: (id: number | null) => void
  onChanged: () => void
}

export function PeoplePage(props: Props) {
  return <div className="content-scroll"><PersonPanel {...props} /></div>
}
