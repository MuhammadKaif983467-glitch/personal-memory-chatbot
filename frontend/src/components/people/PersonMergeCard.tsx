import type { Person } from '../../types'

type Props = {
  persons: Person[]
  excludeId: number
  mergeTarget: number | null
  merging: boolean
  onTargetChange: (id: number | null) => void
  onMerge: () => void
}

export function PersonMergeCard({
  persons,
  excludeId,
  mergeTarget,
  merging,
  onTargetChange,
  onMerge,
}: Props) {
  return (
    <div className="card">
      <h4 style={{ marginTop: 0, fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 12 }}>
        Merge Duplicate People
      </h4>
      <div className="row" style={{ gap: 8 }}>
        <select
          className="input"
          style={{ flex: 1, padding: '8px 12px' }}
          value={mergeTarget ?? ''}
          onChange={(e) => onTargetChange(e.target.value ? Number(e.target.value) : null)}
        >
          <option value="">Select duplicate...</option>
          {persons
            .filter((p) => p.id !== excludeId)
            .map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} ({p.relationship})
              </option>
            ))}
        </select>
        <button
          className="btn btn-ghost"
          onClick={onMerge}
          disabled={merging || mergeTarget == null}
        >
          {merging ? 'Merging...' : 'Merge'}
        </button>
      </div>
    </div>
  )
}
