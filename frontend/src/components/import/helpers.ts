export type PreviewRow = { sender: string; timestamp: string; content: string }
export type ClientPreview = { person: string; title: string; total: number; rows: PreviewRow[] }

export function readFile(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result ?? ''))
    reader.onerror = () => reject(new Error('Could not read the file.'))
    reader.readAsText(file)
  })
}

export function parseCsv(text: string): PreviewRow[] {
  const lines = text.split(/\r?\n/).filter((l) => l.trim().length > 0)
  if (lines.length < 2) return []
  const header = lines[0].split(',').map((c) => c.trim().toLowerCase())
  const si = header.indexOf('sender'), ti = header.indexOf('timestamp'), ci = header.indexOf('content')
  if (si < 0 || ci < 0) return []
  return lines.slice(1).map((line) => {
    const cells = line.split(',')
    return { sender: cells[si] ?? '', timestamp: ti >= 0 ? cells[ti] ?? '' : '', content: cells.slice(ci).join(',').trim() }
  })
}

export function previewFromJson(payload: unknown): ClientPreview {
  const data = (payload ?? {}) as Record<string, unknown>
  const conv = (data.conversation ?? {}) as Record<string, unknown>
  const msgs = Array.isArray(data.messages) ? data.messages : []
  const rows = msgs.map((item) => {
    const m = (item ?? {}) as Record<string, unknown>
    return { sender: String(m.sender ?? ''), timestamp: String(m.timestamp ?? ''), content: String(m.content ?? '') }
  })
  return { person: String(conv.person ?? 'Unknown'), title: String(conv.title ?? 'Untitled'), total: rows.length, rows: rows.slice(0, 5) }
}
