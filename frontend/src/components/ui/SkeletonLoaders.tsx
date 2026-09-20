import { Skeleton } from './Skeleton'

export function MessageSkeleton() {
  return (
    <div className="bubble-row bubble-assistant" style={{ gap: 10 }}>
      <Skeleton variant="circle" width={36} height={36} />
      <div style={{ flex: 1, maxWidth: 520 }}>
        <Skeleton variant="rect" width="100%" height={60} />
      </div>
    </div>
  )
}

export function MemorySkeleton() {
  return (
    <div className="memory-card">
      <div style={{ display: 'flex', gap: 8, marginBottom: 10 }}>
        <Skeleton variant="text" width={60} height={18} />
        <Skeleton variant="text" width={80} height={18} />
        <Skeleton variant="text" width={40} height={18} />
      </div>
      <Skeleton variant="text" width="100%" />
      <Skeleton variant="text" width="90%" />
      <Skeleton variant="text" width="45%" />
    </div>
  )
}

export function PersonSkeleton() {
  return (
    <div className="person-card">
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
        <Skeleton variant="circle" width={36} height={36} />
        <Skeleton variant="text" width={100} height={16} />
      </div>
      <Skeleton variant="text" width="60%" />
      <Skeleton variant="text" width="40%" />
    </div>
  )
}

export function ConversationSkeleton() {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 12px' }}>
      <div style={{ flex: 1 }}>
        <Skeleton variant="text" width="70%" height={14} />
        <div style={{ display: 'flex', gap: 8, marginTop: 6 }}>
          <Skeleton variant="text" width={50} height={10} />
          <Skeleton variant="text" width={30} height={10} />
        </div>
      </div>
    </div>
  )
}
