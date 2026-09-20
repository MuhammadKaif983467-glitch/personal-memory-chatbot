import { useState, useEffect, useCallback } from 'react'
import type { Person, PersonProfile, WritingStyle, MergeResult } from '../../types'
import { api } from '../../services/api'
import { Avatar } from '../ui/Avatar'
import { PersonCard } from './PersonCard'
import { PersonProfileView } from './PersonProfile'
import { WritingStyleCard } from './WritingStyleCard'
import { PersonMergeCard } from './PersonMergeCard'

type Props = {
  persons: Person[]
  selectedPersonId: number | null
  onSelectPerson: (id: number | null) => void
  onChanged: () => void
}

export function PersonShell({ persons, selectedPersonId, onSelectPerson, onChanged }: Props) {
  const [profile, setProfile] = useState<PersonProfile | null>(null)
  const [style, setStyle] = useState<WritingStyle | null>(null)
  const [loading, setLoading] = useState(false)
  const [analyzing, setAnalyzing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [mergeTarget, setMergeTarget] = useState<number | null>(null)
  const [merging, setMerging] = useState(false)
  const sel = persons.find((p) => p.id === selectedPersonId) || null

  const loadData = useCallback(async (id: number) => {
    setLoading(true); setError(null); setNotice(null); setProfile(null); setStyle(null)
    try { const [p, s] = await Promise.all([api.getProfile(id), api.getStyle(id)]); setProfile(p); setStyle(s) }
    catch (e: any) { setError(e?.message || 'Failed to load person data') }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { if (selectedPersonId != null) { loadData(selectedPersonId); setMergeTarget(null) } }, [selectedPersonId, loadData])

  const handleAnalyze = async () => {
    if (selectedPersonId == null) return
    setAnalyzing(true)
    try { await api.analyzePerson(selectedPersonId); setNotice('Analysis complete'); await loadData(selectedPersonId); onChanged() }
    catch (e: any) { setError(e?.message || 'Analysis failed') } finally { setAnalyzing(false) }
  }

  const handleMerge = async () => {
    if (selectedPersonId == null || mergeTarget == null) return
    if (!window.confirm(`Merge into "${persons.find((p) => p.id === mergeTarget)?.name}"? This cannot be undone.`)) return
    setMerging(true)
    try {
      const r: MergeResult = await api.mergePeople(selectedPersonId, mergeTarget)
      setNotice(`Merged: ${r.moved_messages} messages, ${r.moved_conversations} conversations moved.`)
      onSelectPerson(r.to_person_id); onChanged()
    } catch (e: any) { setError(e?.message || 'Merge failed') } finally { setMerging(false) }
  }

  return (
    <div className="panel">
      <header className="panel-head" style={{ background: 'transparent', borderBottom: '1px solid var(--border-subtle)' }}>
        <h2 style={{ fontSize: '1.1rem', fontWeight: 700 }}>People</h2>
        <p className="muted" style={{ fontSize: '0.85rem', marginTop: 4 }}>Profiles, writing styles, and communication analysis</p>
      </header>
      {error && <div className="error" onClick={() => setError(null)}>{error}</div>}
      {notice && <div className="notice status-ok" onClick={() => setNotice(null)}>{notice}</div>}
      <div className="person-cards" style={{ marginTop: 16 }}>
        {persons.map((p) => (
          <PersonCard key={p.id} person={p} isSelected={p.id === selectedPersonId} onClick={() => onSelectPerson(p.id)} />
        ))}
      </div>
      {sel && (
        <div style={{ marginTop: 16 }}>
          <div className="row-between" style={{ marginBottom: 16 }}>
            <span className="row" style={{ gap: 10 }}>
              <Avatar name={sel.name} size="lg" />
              <span>
                <strong style={{ fontSize: '1rem' }}>{sel.name}</strong>
                <span className="muted" style={{ fontSize: '0.8rem', marginLeft: 8 }}>{sel.relationship}</span>
              </span>
            </span>
            <button className="btn btn-ghost" onClick={handleAnalyze} disabled={analyzing}>{analyzing ? 'Analyzing...' : 'Run analysis'}</button>
          </div>
          {loading ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <div className="skeleton skeleton-text" style={{ width: '80%' }} />
              <div className="skeleton skeleton-text" style={{ width: '60%' }} />
              <div className="skeleton skeleton-text" style={{ width: '70%' }} />
            </div>
          ) : (
            <>
              {profile && <PersonProfileView profile={profile} />}
              {style && <WritingStyleCard style={style} />}
              <PersonMergeCard persons={persons} excludeId={sel.id} mergeTarget={mergeTarget} merging={merging} onTargetChange={setMergeTarget} onMerge={handleMerge} />
            </>
          )}
        </div>
      )}
      {!sel && !loading && <div className="empty-state" style={{ padding: 48 }}>Select a person to view their profile.</div>}
    </div>
  )
}
