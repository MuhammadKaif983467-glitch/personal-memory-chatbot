import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { Health, Person, Project } from './types'
import { API_BASE_URL, api } from './services/api'
import { loadPreferences, savePreferences, type Preferences } from './services/preferences'
import { ChatPage } from './pages/ChatPage'
import { MemoriesPage } from './pages/MemoriesPage'
import { PeoplePage } from './pages/PeoplePage'
import { ImportPage } from './pages/ImportPage'
import { SettingsPage } from './pages/SettingsPage'
import { NewProjectModal } from './components/NewProjectModal'

type Tab = 'chat' | 'memories' | 'people' | 'import' | 'settings'

type ConnectionStatus = 'CONNECTING' | 'CONNECTED' | 'DEGRADED' | 'OFFLINE'

const TAB_ITEMS: { key: Tab; icon: string; label: string }[] = [
  { key: 'chat', icon: "\u{1F4AC}", label: 'Chat' },
  { key: 'memories', icon: "\u{1F9E0}", label: 'Memories' },
  { key: 'people', icon: "\u{1F465}", label: 'People' },
  { key: 'import', icon: "\u{1F4E5}", label: 'Import' },
  { key: 'settings', icon: "\u2699\uFE0F", label: 'Settings' },
]

const CONNECTED_POLL_MS = 30_000
const RETRY_POLL_MS = 5_000
const INITIAL_BACKOFF_MS = 1_000
const MAX_BACKOFF_MS = 16_000

export default function App() {
  const [tab, setTab] = useState<Tab>('chat')
  const [persons, setPersons] = useState<Person[]>([])
  const [projects, setProjects] = useState<Project[]>([])
  const [selectedProjectId, setSelectedProjectId] = useState<number | null>(null)
  const [showCreateProject, setShowCreateProject] = useState(false)
  const [selectedPersonId, setSelectedPersonId] = useState<number | null>(null)
  const [health, setHealth] = useState<Health | null>(null)
  const [preferences, setPreferences] = useState<Preferences>(() => loadPreferences())
  const [error, setError] = useState<string | null>(null)
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>('CONNECTING')

  const backoffRef = useRef(INITIAL_BACKOFF_MS)

  const refresh = useCallback(async () => {
    try {
      setError(null)
      setConnectionStatus((prev) => (prev === 'CONNECTED' ? prev : 'CONNECTING'))
      const [nextPersons, nextHealth, nextProjects] = await Promise.all([
        api.listPeople(),
        api.health(),
        api.listProjects(),
      ])
      setPersons(nextPersons)
      setHealth(nextHealth)
      setProjects(nextProjects)
      setConnectionStatus('CONNECTED')
      backoffRef.current = INITIAL_BACKOFF_MS
      setSelectedProjectId((current) =>
        current != null && nextProjects.some((p) => p.id === current) ? current : null,
      )
      setSelectedPersonId((current) =>
        nextPersons.some((p) => p.id === current) ? current : nextPersons[0]?.id ?? null,
      )
    } catch (err) {
      setConnectionStatus('OFFLINE')
      setError(
        err instanceof Error
          ? `${err.message} \u2014 is the backend running at ${API_BASE_URL}?`
          : 'Could not reach the backend API.',
      )
    }
  }, [])

  useEffect(() => {
    let active = true
    let timer: ReturnType<typeof setTimeout> | null = null

    function scheduleNext(delay: number) {
      if (timer != null) clearTimeout(timer)
      timer = setTimeout(async () => {
        if (!active) return
        try {
          const result = await api.health()
          if (!active) return
          setHealth(result)
          setConnectionStatus('CONNECTED')
          backoffRef.current = INITIAL_BACKOFF_MS
          scheduleNext(CONNECTED_POLL_MS)
        } catch {
          if (!active) return
          setConnectionStatus((prev) => (prev === 'CONNECTING' ? 'CONNECTING' : 'OFFLINE'))
          backoffRef.current = Math.min(backoffRef.current * 2, MAX_BACKOFF_MS)
          scheduleNext(RETRY_POLL_MS)
        }
      }, delay)
    }

    void refresh()
    scheduleNext(CONNECTED_POLL_MS)

    return () => {
      active = false
      if (timer != null) clearTimeout(timer)
    }
  }, [refresh])

  const updatePreferences = useCallback((next: Preferences) => {
    setPreferences(next)
    savePreferences(next)
  }, [])

  const projectPersons = useMemo(
    () =>
      selectedProjectId == null
        ? persons
        : persons.filter((person) => person.project_id === selectedProjectId),
    [persons, selectedProjectId],
  )

  const selectedProject = useMemo(
    () => projects.find((p) => p.id === selectedProjectId) ?? null,
    [projects, selectedProjectId],
  )

  const handleRetry = useCallback(() => {
    setConnectionStatus('CONNECTING')
    backoffRef.current = INITIAL_BACKOFF_MS
    void refresh()
  }, [refresh])

  const statusColor =
    connectionStatus === 'CONNECTED'
      ? '#22c55e'
      : connectionStatus === 'CONNECTING' || connectionStatus === 'DEGRADED'
        ? '#eab308'
        : '#ef4444'

  const statusLabel =
    connectionStatus === 'CONNECTED'
      ? 'Connected'
      : connectionStatus === 'CONNECTING'
        ? 'Connecting\u2026'
        : connectionStatus === 'DEGRADED'
          ? 'Degraded'
          : 'Offline'

  return (
    <div className="app" style={S.app}>
      <aside className="sidebar" style={S.sidebar}>
        <div style={S.brand}>
          <div style={S.brandTitle}>
            <span style={S.brandGradient}>Memory</span>
          </div>
          <div style={S.brandSubtitle}>AI Memory Platform</div>
        </div>

        <nav style={S.nav}>
          {TAB_ITEMS.map((item) => {
            const active = tab === item.key
            return (
              <button
                key={item.key}
                type="button"
                onClick={() => setTab(item.key)}
                style={{ ...S.navItem, ...(active ? S.navItemActive : undefined) }}
              >
                <span style={S.navIcon}>{item.icon}</span>
                <span>{item.label}</span>
              </button>
            )
          })}
        </nav>

        <div style={S.projectSection}>
          <div style={S.projectRow}>
            <select
              value={selectedProjectId ?? ''}
              onChange={(e) => {
                const nextId = e.target.value ? Number(e.target.value) : null
                setSelectedProjectId(nextId)
                const scoped =
                  nextId == null
                    ? persons
                    : persons.filter((person) => person.project_id === nextId)
                setSelectedPersonId(scoped[0]?.id ?? null)
              }}
              style={S.projectSelect}
            >
              <option value="">All projects</option>
              {projects.map((project) => (
                <option key={project.id} value={project.id}>
                  {project.name}
                </option>
              ))}
            </select>
            <button
              type="button"
              onClick={() => setShowCreateProject(true)}
              style={S.newProjectBtn}
              title="Create new project"
            >
              +
            </button>
          </div>
          {selectedProject && (
            <div style={S.projectStats}>
              {selectedProject.stats.persons ?? 0} people {'\u00B7'}{' '}
              {selectedProject.stats.conversations ?? 0} conversations {'\u00B7'}{' '}
              {selectedProject.stats.memories ?? 0} memories
            </div>
          )}
        </div>

        <div style={S.spacer} />

        <div style={S.statusBar}>
          <div style={S.statusRow}>
            <span
              style={{
                ...S.statusDot,
                backgroundColor: statusColor,
                animation:
                  connectionStatus === 'CONNECTING'
                    ? 'pulse 1.5s ease-in-out infinite'
                    : undefined,
              }}
            />
            <span style={S.statusLabel}>{statusLabel}</span>
          </div>
          <div style={S.backendUrl}>{API_BASE_URL}</div>
          {connectionStatus === 'OFFLINE' && (
            <button type="button" onClick={handleRetry} style={S.retryBtn}>
              Retry
            </button>
          )}
          {health && (
            <div style={S.providerInfo}>
              {health.provider} v{health.version}
            </div>
          )}
        </div>
      </aside>

      <main className="content" style={S.content}>
        {error && (
          <div style={S.errorBanner}>
            <span>{error}</span>
            <button type="button" onClick={() => setError(null)} style={S.errorDismiss}>
              {'\u2715'}
            </button>
          </div>
        )}

        <div style={S.contentScroll}>
          {tab === 'chat' && (
            <ChatPage
              persons={projectPersons}
              selectedPersonId={selectedPersonId}
              onSelectPerson={setSelectedPersonId}
              showMemorySources={preferences.showMemorySources}
              debugRetrieval={preferences.debugRetrieval}
            />
          )}
          {tab === 'memories' && (
            <MemoriesPage
              persons={projectPersons}
              selectedPersonId={selectedPersonId}
              onSelectPerson={setSelectedPersonId}
            />
          )}
          {tab === 'people' && (
            <PeoplePage
              persons={projectPersons}
              selectedPersonId={selectedPersonId}
              onSelectPerson={setSelectedPersonId}
              onChanged={() => void refresh()}
            />
          )}
          {tab === 'import' && (
            <ImportPage
              onImported={(personId) => {
                void refresh()
                if (personId != null) setSelectedPersonId(personId)
              }}
            />
          )}
          {tab === 'settings' && (
            <SettingsPage preferences={preferences} onPreferences={updatePreferences} />
          )}
        </div>
      </main>

      {showCreateProject && (
        <NewProjectModal
          onCreated={(projectId) => {
            setShowCreateProject(false)
            void refresh().then(() => setSelectedProjectId(projectId))
          }}
          onClose={() => setShowCreateProject(false)}
        />
      )}

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; transform: scale(1); }
          50% { opacity: 0.5; transform: scale(1.4); }
        }
        .app select:focus,
        .app input:focus,
        .app button:focus-visible {
          outline: 2px solid #6366f1;
          outline-offset: 1px;
        }
        .app ::-webkit-scrollbar { width: 6px; }
        .app ::-webkit-scrollbar-track { background: transparent; }
        .app ::-webkit-scrollbar-thumb { background: #334155; border-radius: 3px; }
        .app ::-webkit-scrollbar-thumb:hover { background: #475569; }
      `}</style>
    </div>
  )
}

const S: Record<string, React.CSSProperties> = {
  app: {
    display: 'flex',
    height: '100vh',
    width: '100vw',
    overflow: 'hidden',
    background: '#0f172a',
    color: '#e2e8f0',
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
  },
  sidebar: {
    display: 'flex',
    flexDirection: 'column',
    width: 260,
    minWidth: 260,
    height: '100vh',
    background: '#1e293b',
    borderRight: '1px solid #334155',
    padding: '20px 16px 16px',
    boxSizing: 'border-box',
    overflowY: 'auto',
  },
  brand: {
    marginBottom: 24,
    textAlign: 'center',
  },
  brandTitle: {
    fontSize: 28,
    fontWeight: 800,
    lineHeight: 1.1,
    letterSpacing: '-0.02em',
  },
  brandGradient: {
    background: 'linear-gradient(135deg, #818cf8, #c084fc, #f472b6)',
    WebkitBackgroundClip: 'text',
    WebkitTextFillColor: 'transparent',
    backgroundClip: 'text',
  },
  brandSubtitle: {
    fontSize: 11,
    color: '#94a3b8',
    letterSpacing: '0.06em',
    textTransform: 'uppercase' as const,
    marginTop: 4,
  },
  nav: {
    display: 'flex',
    flexDirection: 'column',
    gap: 2,
    marginBottom: 20,
  },
  navItem: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    padding: '10px 14px',
    borderRadius: 8,
    border: 'none',
    background: 'transparent',
    color: '#94a3b8',
    fontSize: 14,
    fontWeight: 500,
    cursor: 'pointer',
    transition: 'all 0.15s ease',
    textAlign: 'left' as const,
    width: '100%',
  },
  navItemActive: {
    background: 'rgba(99, 102, 241, 0.15)',
    color: '#a5b4fc',
  },
  navIcon: {
    fontSize: 16,
    width: 22,
    textAlign: 'center' as const,
  },
  projectSection: {
    marginBottom: 16,
  },
  projectRow: {
    display: 'flex',
    gap: 6,
    alignItems: 'center',
  },
  projectSelect: {
    flex: 1,
    padding: '8px 10px',
    borderRadius: 6,
    border: '1px solid #334155',
    background: '#0f172a',
    color: '#e2e8f0',
    fontSize: 13,
    cursor: 'pointer',
  },
  newProjectBtn: {
    width: 34,
    height: 34,
    borderRadius: 6,
    border: '1px solid #334155',
    background: '#0f172a',
    color: '#a5b4fc',
    fontSize: 16,
    fontWeight: 700,
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
  },
  projectStats: {
    fontSize: 12,
    color: '#64748b',
    marginTop: 8,
    lineHeight: 1.5,
  },
  spacer: {
    flex: 1,
  },
  statusBar: {
    borderTop: '1px solid #334155',
    paddingTop: 12,
  },
  statusRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    marginBottom: 4,
  },
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: '50%',
    flexShrink: 0,
  },
  statusLabel: {
    fontSize: 13,
    fontWeight: 500,
    color: '#cbd5e1',
  },
  backendUrl: {
    fontSize: 11,
    color: '#475569',
    fontFamily: 'monospace',
    marginTop: 2,
  },
  retryBtn: {
    marginTop: 8,
    padding: '5px 14px',
    borderRadius: 6,
    border: '1px solid #ef4444',
    background: 'transparent',
    color: '#ef4444',
    fontSize: 12,
    fontWeight: 500,
    cursor: 'pointer',
    width: '100%',
  },
  providerInfo: {
    fontSize: 11,
    color: '#475569',
    marginTop: 8,
  },
  content: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden',
    minWidth: 0,
  },
  contentScroll: {
    flex: 1,
    overflow: 'auto',
    minHeight: 0,
  },
  errorBanner: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '10px 16px',
    background: '#451a1a',
    borderBottom: '1px solid #7f1d1d',
    color: '#fca5a5',
    fontSize: 13,
    flexShrink: 0,
  },
  errorDismiss: {
    background: 'transparent',
    border: 'none',
    color: '#fca5a5',
    fontSize: 16,
    cursor: 'pointer',
    padding: '0 4px',
    lineHeight: 1,
  },
}
