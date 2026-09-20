type Row = { sender: string; timestamp: string; content: string }

type Props = { rows: Row[]; person: string; title: string; total: number }

export function ImportPreviewTable({ rows, person, title, total }: Props) {
  return (
    <section className="card">
      <h3>Client-side preview</h3>
      <ul className="report">
        <li>Person: <strong>{person}</strong></li>
        <li>Conversation: <strong>{title}</strong></li>
        <li>Messages detected: <strong>{total}</strong></li>
      </ul>
      {rows.length > 0 ? (
        <table className="preview-table">
          <thead><tr><th>Sender</th><th>Timestamp</th><th>Content</th></tr></thead>
          <tbody>{rows.map((r, i) => <tr key={i}><td>{r.sender}</td><td className="muted">{r.timestamp}</td><td>{r.content}</td></tr>)}</tbody>
        </table>
      ) : (
        <p className="muted">No previewable rows — check the data has sender and content.</p>
      )}
      {total > rows.length && <p className="muted">Showing first {rows.length} of {total} messages.</p>}
    </section>
  )
}
