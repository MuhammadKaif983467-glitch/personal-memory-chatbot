import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { Person, Project } from './types'
import { API_BASE_URL, api } from './services/api'
import { loadPreferences, savePreferences, type Preferences } from './services/preferences'
import { ToastProvider } from './hooks/useToast'
import { ChatShell } from './components/chat'
import { MemoryShell } from './components/memory'
import { PersonShell } from './components/people'
import { ImportShell } from './components/import'
import { SettingsShell } from './components/settings'
import { CreateProjectModal } from './components/projects'
import { EditProjectModal } from './components/projects'
import { GlobalSearch } from './components/search/GlobalSearch'

type Tab = 'chat' | 'memories' | 'people' | 'import' | 'settings'
type ConnectionStatus = 'CONNECTING' | 'CONNECTED' | 'DEGRADED' | 'OFFLINE'

const TAB_ITEMS: { key: Tab; label: string; icon: JSX.Element }[] = [
  {
    key: 'chat',
    label: 'Chat',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
      </svg>
    ),
  },
  {
    key: 'memories',
    label: 'Memories',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="10" />
        <path d="M12 16v-4" />
        <path d="M12 8h.01" />
      </svg>
    ),
  },
  {
    key: 'people',
    label: 'People',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
        <circle cx="9" cy="7" r="4" />
        <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
        <path d="M16 3.13a4 4 0 0 1 0 7.75" />
      </svg>
    ),
  },
  {
    key: 'import',
    label: 'Import',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
        <polyline points="7 10 12 15 17 10" />
        <line x1="12" y1="15" x2="12" y2="3" />
      </svg>
    ),
  },
  {
    key: 'settings',
    label: 'Settings',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="3" />
        <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
      </svg>
    ),
  },
]

const CONNECTED_POLL_MS = 30_000
const RETRY_POLL_MS = 5_000
const INITIAL_BACKOFF_MS = 1_000
const MAX_BACKOFF_MS = 16_000

function AppShell() {
  const [tab, setTab] = useState<Tab>('chat')
  const [persons, setPersons] = useState<Person[]>([])
  const [projects, setProjects] = useState<Project[]>([])
  const [selectedProjectId, setSelectedProjectId] = useState<number | null>(null)
  const [showCreateProject, setShowCreateProject] = useState(false)
  const [showEditProject, setShowEditProject] = useState(false)
  const [showSearch, setShowSearch] = useState(false)
  const [selectedPersonId, setSelectedPersonId] = useState<number | null>(null)
  const [preferences, setPreferences] = useState<Preferences>(() => loadPreferences())
  const [error, setError] = useState<string | null>(null)
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>('CONNECTING')

  const backoffRef = useRef(INITIAL_BACKOFF_MS)

  const refresh = useCallback(async () => {
    try {
      setError(null)
      setConnectionStatus((prev) => (prev === 'CONNECTED' ? prev : 'CONNECTING'))
      const [peopleResult, healthResult, projectsResult] = await Promise.allSettled([
        api.listPeople(),
        api.health(),
        api.listProjects(),
      ])

      if (healthResult.status === 'rejected') {
        setConnectionStatus('OFFLINE')
        setError(
          healthResult.reason instanceof Error
            ? `${healthResult.reason.message} -- is the backend running at ${API_BASE_URL}?`
            : 'Could not reach the backend API.',
        )
        return
      }

      const nextPersons = peopleResult.status === 'fulfilled' ? peopleResult.value : []
      const nextProjects = projectsResult.status === 'fulfilled' ? projectsResult.value : []

      setPersons(nextPersons)
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
          ? `${err.message} -- is the backend running at ${API_BASE_URL}?`
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
          await api.health()
          if (!active) return
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

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        setShowSearch(true)
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [])

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

  const handleProjectChange = useCallback(
    (e: React.ChangeEvent<HTMLSelectElement>) => {
      const nextId = e.target.value ? Number(e.target.value) : null
      setSelectedProjectId(nextId)
      const scoped =
        nextId == null
          ? persons
          : persons.filter((person) => person.project_id === nextId)
      setSelectedPersonId(scoped[0]?.id ?? null)
    },
    [persons],
  )

  const statusDotClass =
    connectionStatus === 'CONNECTED'
      ? 'status-dot'
      : connectionStatus === 'CONNECTING' || connectionStatus === 'DEGRADED'
        ? 'status-dot connecting'
        : 'status-dot offline'

  const statusLabel =
    connectionStatus === 'CONNECTED'
      ? 'Connected'
      : connectionStatus === 'CONNECTING'
        ? 'Connecting...'
        : connectionStatus === 'DEGRADED'
          ? 'Degraded'
          : 'Offline'

  return (
    <div className="app app-layout">
      <aside className="sidebar" aria-label="Main navigation">
        <div className="sidebar-brand">
          <h1>Memory</h1>
        </div>

        <nav className="sidebar-nav" aria-label="Main menu">
          {TAB_ITEMS.map((item) => (
            <button
              key={item.key}
              type="button"
              className={`sidebar-nav-item${tab === item.key ? ' active' : ''}`}
              onClick={() => setTab(item.key)}
              aria-current={tab === item.key ? 'page' : undefined}
            >
              {item.icon}
              <span>{item.label}</span>
            </button>
          ))}
          <button
            type="button"
            className="sidebar-nav-item"
            onClick={() => setShowSearch(true)}
            title="Search (Ctrl+K)"
            aria-label="Search (Ctrl+K)"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
            <span>Search</span>
          </button>
        </nav>

        <div className="sidebar-project-select">
          <div className="row" style={{ gap: 6 }}>
            <select className="input" style={{ flex: 1, padding: '6px 10px', fontSize: '0.8rem' }} value={selectedProjectId ?? ''} onChange={handleProjectChange} aria-label="Select project">
              <option value="">All projects</option>
              {projects.map((project) => (
                <option key={project.id} value={project.id}>
                  {project.name}
                </option>
              ))}
            </select>
            <button type="button" className="icon-btn" onClick={() => setShowCreateProject(true)} title="New project" style={{ width: 32, height: 32 }}>
              +
            </button>
          </div>
          {selectedProject && (
            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: 6, lineHeight: 1.4 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span>
                  {selectedProject.stats.persons ?? 0} people
                  {' '}&middot;{' '}
                  {selectedProject.stats.conversations ?? 0} conversations
                  {' '}&middot;{' '}
                  {selectedProject.stats.memories ?? 0} memories
                </span>
                <button
                  type="button"
                  className="icon-btn"
                  onClick={() => setShowEditProject(true)}
                  title="Edit project"
                  style={{ width: 24, height: 24, fontSize: '0.7rem' }}
                >
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ width: 14, height: 14 }}>
                    <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
                    <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
                  </svg>
                </button>
              </div>
            </div>
          )}
        </div>

        <div className="sidebar-status-bar">
          <div className="row" style={{ gap: 8, flex: 1 }}>
            <span className={statusDotClass} />
            <span>{statusLabel}</span>
          </div>
          {connectionStatus === 'OFFLINE' && (
            <button type="button" className="btn btn-ghost" style={{ padding: '2px 8px', fontSize: '0.7rem' }} onClick={handleRetry}>
              Retry
            </button>
          )}
        </div>
      </aside>

      <main className="main-content">
        {error && (
          <div className="error" onClick={() => setError(null)}>
            <span>{error}</span>
          </div>
        )}

        <div className="content-panel">
          {tab === 'chat' && (
            <ChatShell
              persons={projectPersons}
              selectedPersonId={selectedPersonId}
              onSelectPerson={setSelectedPersonId}
              selectedProjectId={selectedProjectId}
              showMemorySources={preferences.showMemorySources}
              debugRetrieval={preferences.debugRetrieval}
            />
          )}
          {tab === 'memories' && (
            <MemoryShell
              persons={projectPersons}
              selectedPersonId={selectedPersonId}
              onSelectPerson={setSelectedPersonId}
            />
          )}
          {tab === 'people' && (
            <PersonShell
              persons={projectPersons}
              selectedPersonId={selectedPersonId}
              onSelectPerson={setSelectedPersonId}
              onChanged={() => void refresh()}
            />
          )}
          {tab === 'import' && (
            <ImportShell
              projectId={selectedProjectId}
              onImported={(personId) => {
                void refresh()
                if (personId != null) setSelectedPersonId(personId)
              }}
            />
          )}
          {tab === 'settings' && (
            <SettingsShell preferences={preferences} onPreferences={updatePreferences} />
          )}
        </div>
      </main>

      {showCreateProject && (
        <CreateProjectModal
          open={showCreateProject}
          onClose={() => setShowCreateProject(false)}
          onCreated={() => {
            setShowCreateProject(false)
            void refresh()
          }}
        />
      )}

      {showEditProject && selectedProject && (
        <EditProjectModal
          open={showEditProject}
          project={selectedProject}
          onClose={() => setShowEditProject(false)}
          onSaved={() => {
            setShowEditProject(false)
            void refresh()
          }}
          onDeleted={() => {
            setShowEditProject(false)
            setSelectedProjectId(null)
            void refresh()
          }}
        />
      )}

      <GlobalSearch
        open={showSearch}
        onClose={() => setShowSearch(false)}
        projectId={selectedProjectId}
        onSelectConversation={() => {
          setTab('chat')
          setShowSearch(false)
        }}
        onSelectPerson={(id) => {
          setSelectedPersonId(id)
          setShowSearch(false)
        }}
      />
    </div>
  )
}

export default function App() {
  return (
    <ToastProvider>
      <AppShell />
    </ToastProvider>
  )
}
