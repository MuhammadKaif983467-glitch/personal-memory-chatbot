import type { Memory } from '../../types'

type MemoryType = Memory['memory_type']
const MEMORY_TYPES: MemoryType[] = ['FACT', 'PREFERENCE', 'INTEREST', 'RELATIONSHIP', 'EVENT', 'HABIT', 'OPINION', 'CONVERSATION', 'TEMPORARY']
const STATUS_OPTIONS = [
  { value: 'active', label: 'Current only' },
  { value: 'corrected', label: 'Superseded / corrected' },
  { value: 'all', label: 'All (audit)' },
]

interface Props {
  filterType: string
  filterStatus: string
  onFilterTypeChange: (type: string) => void
  onFilterStatusChange: (status: string) => void
}

export default function MemoryFilters({ filterType, filterStatus, onFilterTypeChange, onFilterStatusChange }: Props) {
  return (
    <div className="row" style={{ gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
      <select className="input" style={{ width: 'auto', padding: '6px 10px', fontSize: '0.8rem' }} value={filterType} onChange={e => onFilterTypeChange(e.target.value)}>
        <option value="">All types</option>
        {MEMORY_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
      </select>
      <select className="input" style={{ width: 'auto', padding: '6px 10px', fontSize: '0.8rem' }} value={filterStatus} onChange={e => onFilterStatusChange(e.target.value)}>
        {STATUS_OPTIONS.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
      </select>
    </div>
  )
}
