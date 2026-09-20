import { ChatWindow } from '../components/ChatWindow'
import type { Person } from '../types'

type Props = {
  persons: Person[]
  selectedPersonId: number | null
  onSelectPerson: (id: number | null) => void
  showMemorySources: boolean
  debugRetrieval: boolean
}

export function ChatPage(props: Props) {
  return <ChatWindow {...props} />
}
