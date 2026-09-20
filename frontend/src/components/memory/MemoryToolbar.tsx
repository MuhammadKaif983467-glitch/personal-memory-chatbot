interface Props {
  searchQuery: string
  onSearchChange: (query: string) => void
  onSearch: () => void
  showFilters: boolean
  onToggleFilters: () => void
  hasActiveFilters: boolean
  onClearFilters: () => void
}

export default function MemoryToolbar({ searchQuery, onSearchChange, onSearch, showFilters, onToggleFilters, hasActiveFilters, onClearFilters }: Props) {
  return (
    <div className="row" style={{ gap: 8, marginTop: 16, marginBottom: 16, flexWrap: 'wrap' }}>
      <div className="field" style={{ flex: 1, minWidth: 160, margin: 0 }}>
        <input className="input" type="text" placeholder="Search memories..." value={searchQuery} onChange={e => onSearchChange(e.target.value)} onKeyDown={e => e.key === 'Enter' && onSearch()} />
      </div>
      <button className="btn btn-ghost" onClick={onToggleFilters}>
        {showFilters ? 'Hide filters' : 'Filters'}
      </button>
      {hasActiveFilters && (
        <button className="btn btn-ghost" onClick={onClearFilters}>Clear</button>
      )}
    </div>
  )
}
