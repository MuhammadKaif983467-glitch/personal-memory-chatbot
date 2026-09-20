import type { ImportPreview } from '../../types'

type Props = { preview: ImportPreview }

export function ServerPreview({ preview: sp }: Props) {
  return (
    <section className="card">
      <h3>Server-side preview</h3>
      <ul className="report">
        <li>File: <strong>{sp.file_name}</strong></li>
        <li>Person: <strong>{sp.person || 'auto-from-file'}</strong></li>
        <li>Records: {sp.total_records} · valid: <strong>{sp.valid_messages}</strong> · malformed: {sp.malformed}</li>
      </ul>
      {sp.preview.length > 0 && (
        <table className="preview-table">
          <thead><tr><th>Line</th><th>Sender</th><th>Content</th><th>Type</th></tr></thead>
          <tbody>{sp.preview.map((r, i) => <tr key={i}><td className="muted">{r.line}</td><td>{r.sender}</td><td>{r.content}</td><td className="muted">{r.message_type}</td></tr>)}</tbody>
        </table>
      )}
      {sp.warnings.length > 0 && <div className="error">{sp.warnings.map((w, i) => <div key={i}>{w}</div>)}</div>}
    </section>
  )
}
