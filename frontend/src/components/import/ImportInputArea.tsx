type Format = 'json' | 'csv' | 'txt' | 'zip'

const FORMAT_META: Record<Format, { label: string; icon: string; desc: string }> = {
  json: { label: 'JSON', icon: '{ }', desc: 'Structured import with conversation metadata' },
  csv: { label: 'CSV', icon: '\u229E', desc: 'Tabular data with sender, timestamp, content columns' },
  txt: { label: 'TXT', icon: '\u00B6', desc: 'Plain-text chat log (one message per line)' },
  zip: { label: 'ZIP', icon: '\u26C1', desc: 'Archive containing text/log export' },
}

const EXAMPLE_JSON = `{
  "consent_confirmed": true,
  "conversation": { "title": "Chat with Ali", "person": "Ali", "source": "manual" },
  "messages": [
    { "sender": "Ali", "timestamp": "2026-01-02T12:00:00", "content": "Hello!" },
    { "sender": "Ali", "timestamp": "2026-01-02T12:05:00", "content": "I like playing football" }
  ]
}`

type Props = {
  mode: Format; jsonText: string; jsonFile: File | null; csvPerson: string; csvFile: File | null
  txtPerson: string; txtZipFile: File | null; onJsonTextChange: (v: string) => void
  onJsonFileChange: (f: File | null) => void; onCsvPersonChange: (v: string) => void
  onCsvFileChange: (f: File | null) => void; onTxtPersonChange: (v: string) => void
  onTxtFileChange: (f: File | null) => void
}

export function ImportInputArea({
  mode, jsonText, jsonFile, csvPerson, csvFile, txtPerson, txtZipFile,
  onJsonTextChange, onJsonFileChange, onCsvPersonChange, onCsvFileChange,
  onTxtPersonChange, onTxtFileChange,
}: Props) {
  return (
    <section className="card import-format-card">
      <div className="format-header">
        <span className="format-badge">{FORMAT_META[mode].icon}</span>
        <div><strong>{FORMAT_META[mode].label} Import</strong><p className="muted">{FORMAT_META[mode].desc}</p></div>
      </div>
      {mode === 'json' ? (
        <div className="import-input-area">
          <div className="row wrap">
            <button type="button" className="ghost" onClick={() => onJsonTextChange(EXAMPLE_JSON)}>Load example</button>
            <input type="file" accept="application/json,.json" onChange={(e) => onJsonFileChange(e.target.files?.[0] ?? null)} />
          </div>
          {jsonFile && <p className="notice">File selected: <strong>{jsonFile.name}</strong></p>}
          <textarea className="json-input" value={jsonText} placeholder="Paste an import JSON object here\u2026"
            onChange={(e) => onJsonTextChange(e.target.value)} disabled={jsonFile != null} rows={12} />
        </div>
      ) : mode === 'csv' ? (
        <div className="import-input-area">
          <div className="row wrap">
            <label className="field"><span>Person name</span><input value={csvPerson} onChange={(e) => onCsvPersonChange(e.target.value)} placeholder="Ali" /></label>
            <label className="field"><span>CSV file</span><input type="file" accept="text/csv,.csv" onChange={(e) => onCsvFileChange(e.target.files?.[0] ?? null)} /></label>
          </div>
          {csvFile && <p className="notice">File selected: <strong>{csvFile.name}</strong></p>}
          <p className="muted">CSV needs a header row with at least: <code>sender</code>, <code>timestamp</code>, <code>content</code>.</p>
        </div>
      ) : (
        <div className="import-input-area">
          <div className="row wrap">
            <label className="field">
              <span>Person name {mode === 'zip' && <span className="muted">(optional)</span>}</span>
              <input value={txtPerson} onChange={(e) => onTxtPersonChange(e.target.value)} placeholder={mode === 'zip' ? 'Auto from file name' : 'Ali'} />
            </label>
            <label className="field">
              <span>{mode === 'zip' ? 'ZIP file' : 'TXT file'}</span>
              <input type="file" accept={mode === 'zip' ? '.zip' : 'text/plain,.txt'} onChange={(e) => onTxtFileChange(e.target.files?.[0] ?? null)} />
            </label>
          </div>
          {txtZipFile && <p className="notice">File selected: <strong>{txtZipFile.name}</strong></p>}
          <p className="muted">{mode === 'zip' ? 'A ZIP archive containing a text/log export.' : 'A plain-text chat log. Each non-empty line becomes a message.'}</p>
        </div>
      )}
    </section>
  )
}
