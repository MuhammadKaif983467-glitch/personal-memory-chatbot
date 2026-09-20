import { useState, useEffect, useCallback } from 'react'
import type { Person, PersonProfile, WritingStyle, MergeResult, Fact } from '../types'
import { api } from '../services/api'

type Props = {
  persons: Person[]
  selectedPersonId: number | null
  onSelectPerson: (id: number | null) => void
  onChanged: () => void
}

type ProfileFactsProps = {
  title: string
  facts: Fact[]
}

function ProfileFacts({ title, facts }: ProfileFactsProps) {
  if (!facts || facts.length === 0) return null
  return (
    <div className="facts">
      <h4>{title}</h4>
      <ul>
        {facts.map((f, i) => (
          <li key={i}>
            <span>{f.value}</span>
            {f.confidence < 1 && (
              <span className="muted"> ({Math.round(f.confidence * 100)}%)</span>
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}

export function PersonPanel({ persons, selectedPersonId, 
onSelectPerson, onChanged }: Props) {
  const [profile, setProfile] = useState<PersonProfile | null>(null)
  const [style, setStyle] = useState<WritingStyle | null>(null)
  const [loading, setLoading] = useState(false)
  const [analyzing, setAnalyzing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [memCount, setMemCount] = useState<Record<number, number>>({})
  const [convCount, setConvCount] = useState<Record<number, number>>({})
  const [mergeTarget, setMergeTarget] = useState<number | null>(null)
  const [merging, setMerging] = useState(false)

  const selectedPerson = persons.find((p) => p.id === selectedPersonId) || null

  useEffect(() => {
    let cancelled = false
    async function loadCounts() {
      try {
        const [memRes, convRes] = await Promise.all([
          api.listMemories(),
          api.listConversations(),
        ])
        if (cancelled) return
        const memMap: Record<number, number> = {}
        const convMap: Record<number, number> = {}
        for (const m of memRes || []) {
          const pid = m.person_id
          if (pid != null) memMap[pid] = (memMap[pid] || 0) + 1
        }
        for (const c of convRes || []) {
          const pid = c.person_id
          if (pid != null) convMap[pid] = (convMap[pid] || 0) + 1
        }
        setMemCount(memMap)
        setConvCount(convMap)
      } catch {
        // non-critical
      }
    }
    loadCounts()
    return () => { cancelled = true }
  }, [persons])

  const loadPersonData = useCallback(async (id: number) => {
    setLoading(true)
    setError(null)
    setNotice(null)
    setProfile(null)
    setStyle(null)
    try {
      const [p, s] = await Promise.all([
        api.getProfile(id),
        api.getStyle(id),
      ])
      setProfile(p)
      setStyle(s)
    } catch (e: any) {
      setError(e?.message || 'Failed to load person data')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (selectedPersonId != null) {
      loadPersonData(selectedPersonId)
      setMergeTarget(null)
    }
  }, [selectedPersonId, loadPersonData])

  const handleAnalyze = async () => {
    if (selectedPersonId == null) return
    setAnalyzing(true)
    setError(null)
    setNotice(null)
    try {
      await api.analyzePerson(selectedPersonId)
      setNotice('Analysis complete')
      await loadPersonData(selectedPersonId)
      onChanged()
    } catch (e: any) {
      setError(e?.message || 'Analysis failed')
    } finally {
      setAnalyzing(false)
    }
  }

  const handleMerge = async () => {
    if (selectedPersonId == null || mergeTarget == null) return
    if (!window.confirm(`Merge into "${persons.find((p) => p.id === mergeTarget)?.name}"? This cannot be undone.`)) return
    setMerging(true)
    setError(null)
    setNotice(null)
    try {
      const result: MergeResult = await api.mergePeople(selectedPersonId, mergeTarget)
      setNotice(
        `Merged: ${result.moved_messages} messages, ${result.moved_conversations} conversations moved.`
      )
      onSelectPerson(result.to_person_id)
      onChanged()
    } catch (e: any) {
      setError(e?.message || 'Merge failed')
    } finally {
      setMerging(false)
    }
  }

  return (
    <div className="panel">
      <div className="panel-head">
        <h3>People</h3>
        <select
          className="field"
          value={selectedPersonId ?? ''}
          onChange={(e) => {
            const v = e.target.value
            onSelectPerson(v ? Number(v) : null)
          }}
        >
          <option value="">Select a person...</option>
          {persons.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name} ({p.relationship})
            </option>
          ))}
        </select>
      </div>

      {error && <div className="error">{error}</div>}
      {notice && <div className="notice status-ok">{notice}</div>}

      <div className="person-cards">
        {persons.map((p) => (
          <button
            key={p.id}
            className={`person-card${p.id === selectedPersonId ? ' active' : ''}`}
            onClick={() => onSelectPerson(p.id)}
          >
            <strong>{p.name}</strong>
            <span className="muted">{p.relationship}</span>
            <span>{p.message_count.toLocaleString()} messages</span>
            {(memCount[p.id] ?? 0) > 0 && (
              <span className="muted">{memCount[p.id]} memories</span>
            )}
            {(convCount[p.id] ?? 0) > 0 && (
              <span className="muted">{convCount[p.id]} conversations</span>
            )}
          </button>
        ))}
      </div>

      {selectedPerson && (
        <div className="grow" style={{ overflowY: 'auto' }}>
          <div className="row" style={{ alignItems: 'center', gap: 8, marginBottom: 12 }}>
            <h3 style={{ margin: 0 }}>{selectedPerson.name}</h3>
            <span className="muted">{selectedPerson.relationship}</span>
            <button
              className="ghost"
              onClick={handleAnalyze}
              disabled={analyzing}
              style={{ marginLeft: 'auto' }}
            >
              {analyzing ? 'Analyzing...' : 'Run analysis'}
            </button>
          </div>

          {loading ? (
            <div className="muted">Loading...</div>
          ) : (
            <>
              {profile && (
                <div className="card" style={{ marginBottom: 12 }}>
                  <h4 style={{ marginTop: 0 }}>Profile</h4>
                  <div className="grid two">
                    <div>
                      <ProfileFacts title="Interests" facts={profile.interests} />
                      <ProfileFacts title="Preferences" facts={profile.preferences} />
                    </div>
                    <div>
                      <ProfileFacts title="Important Facts" facts={profile.important_facts} />
                      {profile.communication_habits.length > 0 && (
                        <div className="facts">
                          <h4>Communication Habits</h4>
                          <ul>
                            {profile.communication_habits.map((h, i) => (
                              <li key={i}>{h}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  </div>
                  {profile.topics.length > 0 && (
                    <div className="facts" style={{ marginTop: 8 }}>
                      <h4>Topics</h4>
                      <ul>
                        {profile.topics.map((t, i) => (
                          <li key={i}>
                            {t.value}
                            {t.confidence < 1 && (
                              <span className="muted"> ({Math.round(t.confidence * 100)}%)</span>
                            )}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}

              {style && (
                <div className="card" style={{ marginBottom: 12 }}>
                  <h4 style={{ marginTop: 0 }}>Writing Style</h4>
                  <div className="grid two">
                    <div className="style-list">
                      <div className="field">
                        <span className="muted">Tone:</span> {style.tone || '—'}
                      </div>
                      <div className="field">
                        <span className="muted">Avg message length:</span>{' '}
                        {Math.round(style.average_message_length)} chars
                      </div>
                      <div className="field">
                        <span className="muted">Avg words/message:</span>{' '}
                        {Math.round(style.average_words_per_message)}
                      </div>
                      {Object.keys(style.language_mix).length > 0 && (
                        <div className="field">
                          <span className="muted">Languages:</span>{' '}
                          {Object.entries(style.language_mix)
                            .sort((a, b) => b[1] - a[1])
                            .map(([lang, pct]) => `${lang} ${Math.round(pct * 100)}%`)
                            .join(', ')}
                        </div>
                      )}
                    </div>
                    <div className="style-list">
                      {style.common_words.length > 0 && (
                        <div className="field">
                          <span className="muted">Frequent words:</span>{' '}
                          {style.common_words.slice(0, 12).join(', ')}
                        </div>
                      )}
                      {style.common_phrases.length > 0 && (
                        <div className="field">
                          <span className="muted">Common phrases:</span>{' '}
                          {style.common_phrases.slice(0, 6).map((q) => `"${q}"`).join(', ')}
                        </div>
                      )}
                      {style.common_greetings.length > 0 && (
                        <div className="field">
                          <span className="muted">Greetings:</span>{' '}
                          {style.common_greetings.join(', ')}
                        </div>
                      )}
                      {style.common_endings.length > 0 && (
                        <div className="field">
                          <span className="muted">Endings:</span>{' '}
                          {style.common_endings.join(', ')}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )}

              <div className="card">
                <h4 style={{ marginTop: 0 }}>Merge Duplicate People</h4>
                <div className="row" style={{ alignItems: 'center', gap: 8 }}>
                  <select
                    className="field"
                    value={mergeTarget ?? ''}
                    onChange={(e) => {
                      const v = e.target.value
                      setMergeTarget(v ? Number(v) : null)
                    }}
                  >
                    <option value="">Select duplicate...</option>
                    {persons
                      .filter((p) => p.id !== selectedPersonId)
                      .map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.name} ({p.relationship})
                        </option>
                      ))}
                  </select>
                  <button
                    className="ghost"
                    onClick={handleMerge}
                    disabled={merging || mergeTarget == null}
                  >
                    {merging ? 'Merging...' : 'Merge'}
                  </button>
                </div>
              </div>
            </>
          )}
        </div>
      )}

      {!selectedPerson && !loading && (
        <div className="muted grow" style={{ padding: 24, textAlign: 'center' }}>
          Select a person to view their profile.
        </div>
      )}
    </div>
  )
}
