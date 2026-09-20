import type { WritingStyle } from '../../types'

type Props = {
  style: WritingStyle
}

export function WritingStyleCard({ style }: Props) {
  return (
    <div className="card" style={{ marginBottom: 16 }}>
      <h4 style={{ marginTop: 0, fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 12 }}>
        Writing Style
      </h4>
      <div className="grid-2">
        <div className="style-list">
          <li><span className="muted">Tone:</span> {style.tone || '—'}</li>
          <li><span className="muted">Avg message:</span> {Math.round(style.average_message_length)} chars</li>
          <li><span className="muted">Avg words/msg:</span> {Math.round(style.average_words_per_message)}</li>
          {Object.keys(style.language_mix).length > 0 && (
            <li><span className="muted">Languages:</span>{' '}
              {Object.entries(style.language_mix)
                .sort((a, b) => b[1] - a[1])
                .map(([lang, pct]) => `${lang} ${Math.round(pct * 100)}%`)
                .join(', ')}
            </li>
          )}
        </div>
        <div className="style-list">
          {style.common_words.length > 0 && (
            <li><span className="muted">Frequent words:</span> {style.common_words.slice(0, 12).join(', ')}</li>
          )}
          {style.common_phrases.length > 0 && (
            <li><span className="muted">Common phrases:</span> {style.common_phrases.slice(0, 6).map((q) => `"${q}"`).join(', ')}</li>
          )}
          {style.common_greetings.length > 0 && (
            <li><span className="muted">Greetings:</span> {style.common_greetings.join(', ')}</li>
          )}
          {style.common_endings.length > 0 && (
            <li><span className="muted">Sign-offs:</span> {style.common_endings.join(', ')}</li>
          )}
        </div>
      </div>
    </div>
  )
}
