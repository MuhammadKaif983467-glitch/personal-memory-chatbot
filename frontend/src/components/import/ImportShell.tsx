import { useState, useCallback } from 'react'
import type { ImportPreview, ImportResult } from '../../types'
import { api, errText } from '../../services/api'
import { ImportPreviewTable } from './ImportPreviewTable'
import { ImportReport } from './ImportReport'
import { ImportProgress } from './ImportProgress'

type Stage = 'idle' | 'detecting' | 'previewing' | 'uploading' | 'done'
const STAGE_LABEL: Record<Stage, string> = {
  idle: 'Ready',
  detecting: 'Detecting format...',
  previewing: 'Loading preview...',
  uploading: 'Importing...',
  done: 'Done',
}

type Props = {
  onImported: (personId?: number | null) => void
  projectId?: number | null
}

const PLATFORM_ICONS: Record<string, string> = {
  whatsapp: '💬',
  telegram: '✈️',
  instagram: '📸',
  facebook: '👤',
  generic: '📄',
  unknown: '❓',
}

const PLATFORM_LABELS: Record<string, string> = {
  whatsapp: 'WhatsApp',
  telegram: 'Telegram',
  instagram: 'Instagram',
  facebook: 'Facebook / Messenger',
  generic: 'Generic',
  unknown: 'Unknown',
}

export function ImportShell({ onImported, projectId }: Props) {
  const [file, setFile] = useState<File | null>(null)
  const [person, setPerson] = useState('')
  const [consent, setConsent] = useState(false)
  const [stage, setStage] = useState<Stage>('idle')
  const [error, setError] = useState<string | null>(null)
  const [preview, setPreview] = useState<ImportPreview | null>(null)
  const [report, setReport] = useState<ImportResult | null>(null)
  const [platform, setPlatform] = useState<string>('')
  const [participants, setParticipants] = useState<string[]>([])
  const busy = stage !== 'idle' && stage !== 'done'

  const handleFileChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0] ?? null
    setFile(f)
    setPreview(null)
    setReport(null)
    setPlatform('')
    setParticipants([])
    setError(null)
    setStage('idle')
  }, [])

  const handlePreview = useCallback(async () => {
    if (!file) { setError('Choose a file first.'); return }
    setError(null)
    setStage('detecting')
    try {
      const result = await api.universalPreview(file, person.trim())
      setPreview(result)
      setPlatform(result.platform || result.source || 'unknown')
      setParticipants(result.participants || [])
      setStage('idle')
    } catch (err) {
      setStage('idle')
      setError(errText(err, 'Could not preview file.'))
    }
  }, [file, person])

  const handleImport = useCallback(async () => {
    if (!file) { setError('Choose a file first.'); return }
    if (!consent) { setError('You must confirm consent before importing.'); return }
    setError(null)
    setReport(null)
    setStage('uploading')
    try {
      const result = await api.universalImport(file, person.trim() || 'Unknown', true, projectId)
      setReport(result)
      setStage('done')
      onImported(result.person_id ?? null)
    } catch (err) {
      setStage('idle')
      setError(errText(err, 'Import failed.'))
    }
  }, [file, consent, person, projectId, onImported])

  const detectedPlatform = platform || 'unknown'

  return (
    <div className="panel">
      <header className="panel-head">
        <h2>Import conversations</h2>
        <p className="muted">
          Upload chat exports from WhatsApp, Telegram, Instagram, Messenger, or generic files.
          Platform is auto-detected.
        </p>
      </header>

      <section className="card import-format-card">
        <div className="format-header">
          <span className="format-badge">📁</span>
          <div>
            <strong>Universal Import</strong>
            <p className="muted">Supports WhatsApp, Telegram, Instagram, Messenger, TXT, CSV, JSON, ZIP</p>
          </div>
        </div>
        <div className="import-input-area">
          <div className="row wrap">
            <label className="field">
              <span>Person name {platform && <span className="muted">(auto-detected)</span>}</span>
              <input
                value={person}
                onChange={(e) => setPerson(e.target.value)}
                placeholder="Auto-detect from file"
              />
            </label>
            <label className="field">
              <span>Chat file</span>
              <input
                type="file"
                accept=".txt,.csv,.json,.jsonl,.ndjson,.zip,.html,.htm"
                onChange={handleFileChange}
              />
            </label>
          </div>
          {file && (
            <p className="notice">
              File: <strong>{file.name}</strong> ({(file.size / 1024).toFixed(1)} KB)
            </p>
          )}
        </div>
      </section>

      {platform && (
        <section className="card">
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12 }}>
            <span style={{ fontSize: '1.5rem' }}>{PLATFORM_ICONS[detectedPlatform] || '📄'}</span>
            <div>
              <strong>Detected: {PLATFORM_LABELS[detectedPlatform] || detectedPlatform}</strong>
              {preview && (
                <p className="muted" style={{ margin: 0, fontSize: '0.85rem' }}>
                  {preview.valid_messages} messages found
                  {participants.length > 0 && ` · ${participants.length} participant${participants.length > 1 ? 's' : ''}`}
                </p>
              )}
            </div>
          </div>
          {participants.length > 0 && (
            <div style={{ marginTop: 8 }}>
              <span className="muted" style={{ fontSize: '0.85rem' }}>Participants: </span>
              {participants.map((p, i) => (
                <span key={i} className="chip" style={{ marginRight: 4 }}>{p}</span>
              ))}
            </div>
          )}
        </section>
      )}

      <label className="consent">
        <input
          type="checkbox"
          checked={consent}
          onChange={(e) => setConsent(e.target.checked)}
        />
        <span>I confirm I have consent to process this conversation data.</span>
      </label>

      <div className="row">
        <button
          type="button"
          className="ghost"
          onClick={handlePreview}
          disabled={busy || !file}
        >
          Detect & Preview
        </button>
        <button
          type="button"
          onClick={handleImport}
          disabled={busy || !file || !consent}
        >
          {busy ? STAGE_LABEL[stage] : 'Import'}
        </button>
      </div>

      {busy && <ImportProgress stage={stage === 'detecting' || stage === 'previewing' ? 'validating' : stage === 'uploading' ? 'uploading' : 'idle'} />}
      {error && <div className="error" onClick={() => setError(null)}>{error}</div>}
      {preview && (
        <ImportPreviewTable
          rows={preview.preview.map((p) => ({
            sender: p.sender,
            timestamp: typeof p.timestamp === 'string' ? p.timestamp : String(p.timestamp ?? ''),
            content: p.content,
          }))}
          person={preview.person}
          title={preview.file_name}
          total={preview.valid_messages}
        />
      )}
      {report && <ImportReport report={report} />}
    </div>
  )
}
