import { useState } from 'react'
import type { ImportPreview, ImportResult } from '../types'
import { api, errText } from '../services/api'

type Props = {
  onImported: (personId?: number | null) => void
}

type PreviewRow = { sender: string; timestamp: string; content: string }

type Preview = {
  person: string
  title: string
  total: number
  rows: PreviewRow[]
}

type Stage = 'idle' | 'validating' | 'uploading' | 'analyzing' | 'done'

type Format = 'json' | 'csv' | 'txt' | 'zip'

const STAGE_LABEL: Record<Stage, string> = {
  idle: 'Ready',
  validating: 'Validating data…',
  uploading: 'Uploading conversation…',
  analyzing: 'Storing & analyzing…',
  done: 'Import complete',
}

const FORMAT_META: Record<Format, { label: string; icon: string; desc: string }> = {
  json: { label: 'JSON', icon: '{ }', desc: 'Structured import with conversation metadata' },
  csv: { label: 'CSV', icon: '\u229E', desc: 'Tabular data with sender, timestamp, content columns' },
  txt: { label: 'TXT', icon: '\u00B6', desc: 'Plain-text chat log (one message per line)' },
  zip: { label: 'ZIP', icon: '\u26C1', desc: 'Archive containing text/log export' },
}

const EXAMPLE_JSON = `{
  "consent_confirmed": true,
  "conversation": {
    "title": "Chat with Ali",
    "person": "Ali",
    "source": "manual"
  },
  "messages": [
    { "sender": "Ali", "timestamp": "2026-01-02T12:00:00", "content": "Hello! How are you?" },
    { "sender": "Ali", "timestamp": "2026-01-02T12:05:00", "content": "Actually I prefer chai over coffee" },
    { "sender": "Ali", "timestamp": "2026-01-02T12:06:00", "content": "I like playing football and cricket" }
  ]
}`

function readFile(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result ?? ''))
    reader.onerror = () => reject(new Error('Could not read the file.'))
    reader.readAsText(file)
  })
}

function parseCsv(text: string): PreviewRow[] {
  const lines = text.split(/\r?\n/).filter((line) => line.trim().length > 0)
  if (lines.length < 2) return []
  const header = lines[0].split(',').map((cell) => cell.trim().toLowerCase())
  const senderIdx = header.indexOf('sender')
  const timeIdx = header.indexOf('timestamp')
  const contentIdx = header.indexOf('content')
  if (senderIdx < 0 || contentIdx < 0) return []
  return lines.slice(1).map((line) => {
    const cells = line.split(',')
    return {
      sender: cells[senderIdx] ?? '',
      timestamp: timeIdx >= 0 ? cells[timeIdx] ?? '' : '',
      content: cells.slice(contentIdx).join(',').trim(),
    }
  })
}

function previewFromJson(payload: unknown): Preview {
  const data = (payload ?? {}) as Record<string, unknown>
  const conversation = (data.conversation ?? {}) as Record<string, unknown>
  const rawMessages = Array.isArray(data.messages) ? data.messages : []
  const rows = rawMessages.map((item) => {
    const message = (item ?? {}) as Record<string, unknown>
    return {
      sender: String(message.sender ?? ''),
      timestamp: String(message.timestamp ?? ''),
      content: String(message.content ?? ''),
    }
  })
  return {
    person: String(conversation.person ?? 'Unknown'),
    title: String(conversation.title ?? 'Untitled conversation'),
    total: rows.length,
    rows: rows.slice(0, 5),
  }
}

function stageProgress(stage: Stage): number {
  switch (stage) {
    case 'validating': return 30
    case 'uploading': return 60
    case 'analyzing': return 85
    case 'done': return 100
    default: return 0
  }
}

export function ImportPanel({ onImported }: Props) {
  const [mode, setMode] = useState<Format>('json')
  const [jsonText, setJsonText] = useState('')
  const [consent, setConsent] = useState(false)
  const [csvPerson, setCsvPerson] = useState('')
  const [csvFile, setCsvFile] = useState<File | null>(null)
  const [jsonFile, setJsonFile] = useState<File | null>(null)
  const [txtPerson, setTxtPerson] = useState('')
  const [txtZipFile, setTxtZipFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<Preview | null>(null)
  const [serverPreview, setServerPreview] = useState<ImportPreview | null>(null)
  const [report, setReport] = useState<ImportResult | null>(null)
  const [stage, setStage] = useState<Stage>('idle')
  const [error, setError] = useState<string | null>(null)
  const busy = stage === 'validating' || stage === 'uploading' || stage === 'analyzing'

  async function currentJsonText(): Promise<string> {
    if (jsonFile) return readFile(jsonFile)
    return jsonText
  }

  function switchMode(next: Format) {
    setMode(next)
    setPreview(null)
    setServerPreview(null)
    setError(null)
  }

  async function buildPreview() {
    setError(null)
    try {
      setStage('validating')
      if (mode === 'json') {
        const text = await currentJsonText()
        if (!text.trim()) throw new Error('Paste JSON or choose a file first.')
        setPreview(previewFromJson(JSON.parse(text)))
      } else if (mode === 'csv') {
        if (!csvFile) throw new Error('Choose a CSV file first.')
        const rows = parseCsv(await readFile(csvFile))
        setPreview({
          person: csvPerson.trim() || 'Unknown',
          title: csvFile.name,
          total: rows.length,
          rows: rows.slice(0, 5),
        })
      } else {
        if (!txtZipFile) throw new Error('Choose a file first.')
        setServerPreview(await api.importPreview(txtZipFile, txtPerson.trim()))
        setPreview(null)
      }
      setStage('idle')
    } catch (err) {
      setStage('idle')
      setPreview(null)
      setServerPreview(null)
      setError(errText(err, 'Could not preview the data.'))
    }
  }

  async function runImport() {
    if (!consent) {
      setError('You must confirm consent before importing someone else`s messages.')
      return
    }
    setError(null)
    setReport(null)
    setStage('validating')
    try {
      let result: ImportResult
      if (mode === 'json') {
        const text = await currentJsonText()
        const payload = JSON.parse(text) as Record<string, unknown>
        payload.consent_confirmed = true
        setStage('uploading')
        result = await api.importJson(payload)
      } else if (mode === 'csv') {
        if (!csvFile) throw new Error('Choose a CSV file first.')
        if (!csvPerson.trim()) throw new Error('Enter the person name for the CSV import.')
        setStage('uploading')
        result = await api.importCsv(csvFile, csvPerson.trim(), true)
      } else {
        if (!txtZipFile) throw new Error('Choose a file first.')
        const person = txtPerson.trim()
        if (mode === 'txt' && !person) throw new Error('Enter the person name for the TXT import.')
        setStage('uploading')
        result =
          mode === 'txt'
            ? await api.importTxt(txtZipFile, person, true)
            : await api.importZip(txtZipFile, person, true)
      }
      setStage('done')
      setReport(result)
      onImported(result.person_id ?? null)
    } catch (err) {
      setStage('idle')
      setError(errText(err, 'Import failed.'))
    }
  }

  return (
    <div className="panel">
      <header className="panel-head">
        <h2>Import conversation history</h2>
        <p className="muted">Load chat data from a file and bring it into your assistant's memory</p>
      </header>

      <div className="format-tabs row wrap">
        {(Object.keys(FORMAT_META) as Format[]).map((fmt) => (
          <button
            key={fmt}
            type="button"
            className={`format-tab ${mode === fmt ? 'active' : 'ghost'}`}
            onClick={() => switchMode(fmt)}
          >
            <span className="format-icon">{FORMAT_META[fmt].icon}</span>
            <span className="format-label">{FORMAT_META[fmt].label}</span>
          </button>
        ))}
      </div>

      <section className="card import-format-card">
        <div className="format-header">
          <span className="format-badge">{FORMAT_META[mode].icon}</span>
          <div>
            <strong>{FORMAT_META[mode].label} Import</strong>
            <p className="muted">{FORMAT_META[mode].desc}</p>
          </div>
        </div>

        {mode === 'json' ? (
          <div className="import-input-area">
            <div className="row wrap">
              <button type="button" className="ghost" onClick={() => setJsonText(EXAMPLE_JSON)}>
                Load example
              </button>
              <input
                type="file"
                accept="application/json,.json"
                onChange={(e) => {
                  setJsonFile(e.target.files?.[0] ?? null)
                  setPreview(null)
                }}
              />
            </div>
            {jsonFile && (
              <p className="notice">File selected: <strong>{jsonFile.name}</strong></p>
            )}
            <textarea
              className="json-input"
              value={jsonText}
              placeholder="Paste an import JSON object here…"
              onChange={(e) => {
                setJsonText(e.target.value)
                setPreview(null)
              }}
              disabled={jsonFile != null}
              rows={12}
            />
          </div>
        ) : mode === 'csv' ? (
          <div className="import-input-area">
            <div className="row wrap">
              <label className="field">
                <span>Person name</span>
                <input value={csvPerson} onChange={(e) => setCsvPerson(e.target.value)} placeholder="Ali" />
              </label>
              <label className="field">
                <span>CSV file</span>
                <input
                  type="file"
                  accept="text/csv,.csv"
                  onChange={(e) => {
                    setCsvFile(e.target.files?.[0] ?? null)
                    setPreview(null)
                  }}
                />
              </label>
            </div>
            {csvFile && (
              <p className="notice">File selected: <strong>{csvFile.name}</strong></p>
            )}
            <p className="muted">CSV needs a header row with at least: <code>sender</code>, <code>timestamp</code>, <code>content</code>.</p>
          </div>
        ) : (
          <div className="import-input-area">
            <div className="row wrap">
              <label className="field">
                <span>Person name {mode === 'zip' && <span className="muted">(optional)</span>}</span>
                <input
                  value={txtPerson}
                  onChange={(e) => setTxtPerson(e.target.value)}
                  placeholder={mode === 'zip' ? 'Auto from file name' : 'Ali'}
                />
              </label>
              <label className="field">
                <span>{mode === 'zip' ? 'ZIP file' : 'TXT file'}</span>
                <input
                  type="file"
                  accept={mode === 'zip' ? '.zip' : 'text/plain,.txt'}
                  onChange={(e) => {
                    setTxtZipFile(e.target.files?.[0] ?? null)
                    setServerPreview(null)
                  }}
                />
              </label>
            </div>
            {txtZipFile && (
              <p className="notice">File selected: <strong>{txtZipFile.name}</strong></p>
            )}
            {mode === 'zip' ? (
              <p className="muted">
                A ZIP archive containing a text/log export. The largest text member is imported.
              </p>
            ) : (
              <p className="muted">
                A plain-text chat log. Each non-empty line becomes a message; a leading
                &quot;sender: message&quot; prefix is used when present.
              </p>
            )}
          </div>
        )}
      </section>

      <label className="consent">
        <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
        <span>
          I confirm I have permission (consent) to process this conversation data. Consent is
          required before any storage or analysis.
        </span>
      </label>

      <div className="row">
        <button type="button" className="ghost" onClick={() => void buildPreview()} disabled={busy}>
          Preview
        </button>
        <button type="button" onClick={() => void runImport()} disabled={busy || !consent}>
          {busy ? STAGE_LABEL[stage] : 'Import'}
        </button>
      </div>

      {busy && (
        <div className="progress" role="status" aria-live="polite">
          <div className="progress-bar" style={{ width: `${stageProgress(stage)}%` }} />
          <span>{STAGE_LABEL[stage]}</span>
        </div>
      )}

      {error && <div className="error">{error}</div>}

      {preview && (
        <section className="card">
          <h3>Client-side preview</h3>
          <ul className="report">
            <li>Person: <strong>{preview.person}</strong></li>
            <li>Conversation: <strong>{preview.title}</strong></li>
            <li>Messages detected: <strong>{preview.total}</strong></li>
          </ul>
          <table className="preview-table">
            <thead>
              <tr>
                <th>Sender</th>
                <th>Timestamp</th>
                <th>Content</th>
              </tr>
            </thead>
            <tbody>
              {preview.rows.map((row, index) => (
                <tr key={index}>
                  <td>{row.sender}</td>
                  <td className="muted">{row.timestamp}</td>
                  <td>{row.content}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {preview.rows.length === 0 && (
            <p className="muted">No previewable rows — check the data has sender and content.</p>
          )}
          {preview.total > preview.rows.length && (
            <p className="muted">Showing first {preview.rows.length} of {preview.total} messages.</p>
          )}
        </section>
      )}

      {serverPreview && (
        <section className="card">
          <h3>Server-side preview</h3>
          <ul className="report">
            <li>File: <strong>{serverPreview.file_name}</strong></li>
            <li>Person: <strong>{serverPreview.person || 'auto-from-file'}</strong></li>
            <li>
              Records: {serverPreview.total_records} · valid messages:{' '}
              <strong>{serverPreview.valid_messages}</strong> · malformed: {serverPreview.malformed} · empty:{' '}
              {serverPreview.empty}
            </li>
          </ul>
          {serverPreview.preview.length > 0 ? (
            <table className="preview-table">
              <thead>
                <tr>
                  <th>Line</th>
                  <th>Sender</th>
                  <th>Timestamp</th>
                  <th>Content</th>
                  <th>Type</th>
                </tr>
              </thead>
              <tbody>
                {serverPreview.preview.map((row, index) => (
                  <tr key={index}>
                    <td className="muted">{row.line}</td>
                    <td>{row.sender}</td>
                    <td className="muted">{String(row.timestamp ?? '')}</td>
                    <td>{row.content}</td>
                    <td className="muted">{row.message_type}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="muted">No previewable rows.</p>
          )}
          {serverPreview.warnings.length > 0 && (
            <div className="error">
              {serverPreview.warnings.map((warning, index) => (
                <div key={index}>{warning}</div>
              ))}
            </div>
          )}
          <p className="muted">
            Read-only preview (nothing stored). Confirm consent above, then press Import to apply.
          </p>
        </section>
      )}

      {report && (
        <section className="card">
          <h3>Import report</h3>
          <ul className="report">
            <li>Person: <strong>{report.person_name}</strong></li>
            <li>Conversation: <strong>{report.conversation_title}</strong></li>
            <li>Total messages: {report.total}</li>
            <li>Imported: <strong>{report.imported}</strong></li>
            <li>Skipped: {report.skipped}</li>
            <li>Removed empty: {report.removed_empty}</li>
            <li>Removed duplicates: {report.removed_duplicates}</li>
            <li>Removed system: {report.removed_system}</li>
            <li>Spam flagged: {report.spam_flagged}</li>
            <li>Messages created: {report.messages_created}</li>
          </ul>
          {report.errors.length > 0 && (
            <div className="error">
              {report.errors.map((message, index) => (
                <div key={index}>{message}</div>
              ))}
            </div>
          )}
        </section>
      )}
    </div>
  )
}