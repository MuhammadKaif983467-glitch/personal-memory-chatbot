import MemoryPanel from '../components/MemoryPanel'
import type { Person } from '../types'

type Props = {
  persons: Person[]
  selectedPersonId: number | null
  onSelectPerson: (id: number | null) => void
}

export function MemoriesPage(props: Props) {
  return <div className="content-scroll"><MemoryPanel {...props} /></div>
}
