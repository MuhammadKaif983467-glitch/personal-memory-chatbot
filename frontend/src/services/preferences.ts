export type Preferences = {
  showMemorySources: boolean
  debugRetrieval: boolean
}

const STORAGE_KEY = 'pmc.preferences'

const DEFAULTS: Preferences = {
  showMemorySources: true,
  debugRetrieval: false,
}

export function loadPreferences(): Preferences {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (!raw) return { ...DEFAULTS }
    const parsed = JSON.parse(raw) as Partial<Preferences>
    return {
      showMemorySources:
        typeof parsed.showMemorySources === 'boolean'
          ? parsed.showMemorySources
          : DEFAULTS.showMemorySources,
      debugRetrieval:
        typeof parsed.debugRetrieval === 'boolean'
          ? parsed.debugRetrieval
          : DEFAULTS.debugRetrieval,
    }
  } catch {
    return { ...DEFAULTS }
  }
}

export function savePreferences(preferences: Preferences): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(preferences))
  } catch {
    // Storage can be unavailable (private mode); preferences stay in memory.
  }
}
