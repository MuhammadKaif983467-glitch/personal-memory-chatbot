import { Avatar } from '../ui/Avatar'

type Props = {
  personName: string
  hasPerson: boolean
  hasConversation: boolean
}

export function EmptyConversation({ personName, hasPerson, hasConversation }: Props) {
  if (!hasPerson) {
    return (
      <div className="transcript">
        <div className="empty-state">Select a person to start chatting.</div>
      </div>
    )
  }

  return (
    <div className="transcript">
      <div className="empty-state">
        <Avatar name={personName} size="lg" />
        {hasConversation
          ? 'No messages yet.'
          : `Start a conversation with ${personName}.`}
      </div>
    </div>
  )
}
