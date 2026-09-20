type Format = 'json' | 'csv' | 'txt' | 'zip'

const FORMAT_META: Record<Format, { label: string; icon: string }> = {
  json: { label: 'JSON', icon: '{ }' },
  csv: { label: 'CSV', icon: '\u229E' },
  txt: { label: 'TXT', icon: '\u00B6' },
  zip: { label: 'ZIP', icon: '\u26C1' },
}

type Props = { mode: Format; onChange: (fmt: Format) => void }

export function ImportFormatTabs({ mode, onChange }: Props) {
  return (
    <div className="format-tabs row wrap">
      {(Object.keys(FORMAT_META) as Format[]).map((fmt) => (
        <button
          key={fmt}
          type="button"
          className={`format-tab ${mode === fmt ? 'active' : 'ghost'}`}
          onClick={() => onChange(fmt)}
        >
          <span className="format-icon">{FORMAT_META[fmt].icon}</span>
          <span className="format-label">{FORMAT_META[fmt].label}</span>
        </button>
      ))}
    </div>
  )
}
