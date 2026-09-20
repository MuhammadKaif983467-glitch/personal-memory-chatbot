import type { ImportResult } from '../../types'

type Props = { report: ImportResult }

export function ImportReport({ report }: Props) {
  return (
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
      {report.errors.length > 0 && <div className="error">{report.errors.map((m, i) => <div key={i}>{m}</div>)}</div>}
    </section>
  )
}
