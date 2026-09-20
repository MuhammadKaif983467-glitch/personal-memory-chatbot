import type { PersonProfile as Profile, Fact } from '../../types'

type Props = {
  profile: Profile
}

function FactList({ title, facts }: { title: string; facts: Fact[] }) {
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

export function PersonProfileView({ profile }: Props) {
  return (
    <div className="card" style={{ marginBottom: 16 }}>
      <h4 style={{ marginTop: 0, fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 12 }}>
        Profile
      </h4>
      <div className="grid-2">
        <div>
          <FactList title="Interests" facts={profile.interests} />
          <FactList title="Preferences" facts={profile.preferences} />
        </div>
        <div>
          <FactList title="Important Facts" facts={profile.important_facts} />
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
  )
}
