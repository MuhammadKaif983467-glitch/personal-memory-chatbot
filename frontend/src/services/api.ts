import type {
  AppSettings,
  ChatResponse,
  Conversation,
  ConversationDeleteResult,
  Health,
  ImportPreview,
  ImportResult,
  Memory,
  MemoryVersion,
  MergeResult,
  MessageRecord,
  Person,
  PersonProfile,
  Project,
  ProjectCreatePayload,
  ProjectDetail,
  VoiceStatus,
  WritingStyle,
} from '../types'

const API_BASE: string =
  (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, '') ||
  'http://localhost:8000'

export class ApiError extends Error {
  status: number
  details: unknown

  constructor(message: string, status: number, details?: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.details = details
  }
}

type RequestOptions = {
  method?: string
  body?: unknown
  formData?: FormData
  query?: Record<string, string | number | undefined>
}

const REQUEST_TIMEOUT_MS = 30_000

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, formData, query } = options
  let url = `${API_BASE}${path}`
  if (query) {
    const params = new URLSearchParams()
    for (const [key, value] of Object.entries(query)) {
      if (value !== undefined) params.set(key, String(value))
    }
    const qs = params.toString()
    if (qs) url += `?${qs}`
  }

  const init: RequestInit = { method }
  const controller = new AbortController()
  const timer = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS)
  init.signal = controller.signal

  if (formData) {
    init.body = formData
  } else if (body !== undefined) {
    init.headers = { 'Content-Type': 'application/json' }
    init.body = JSON.stringify(body)
  }

  let response: Response
  try {
    response = await fetch(url, init)
  } catch (err) {
    window.clearTimeout(timer)
    if (err instanceof Error && err.name === 'AbortError') {
      throw new ApiError('The request took too long. Check that the backend is running.', 0)
    }
    throw new ApiError('Could not reach the backend. Check that it is running.', 0)
  }
  window.clearTimeout(timer)

  if (response.status === 204) return undefined as T

  const text = await response.text()
  const payload = text ? safeJson(text) : null

  if (!response.ok) {
    const detail = (payload as { detail?: unknown } | null)?.detail
    const message = extractMessage(detail) || friendlyStatus(response.status)
    throw new ApiError(message, response.status, detail)
  }
  return payload as T
}

function friendlyStatus(status: number): string {
  if (status === 400) return 'The request was invalid.'
  if (status === 401 || status === 403) return 'Not authorised for this action.'
  if (status === 404) return 'That item was not found.'
  if (status === 429) return 'Rate limited - please wait a moment and try again.'
  if (status >= 500) return 'The server ran into a problem. Check the backend logs.'
  return `Request failed with status ${status}`
}

/** Human-readable error text for the UI, centralised here. */
export function errText(err: unknown, fallback = 'Something went wrong.'): string {
  return err instanceof Error && err.message ? err.message : fallback
}

function safeJson(text: string): unknown {
  try {
    return JSON.parse(text)
  } catch {
    return text
  }
}

function extractMessage(detail: unknown): string {
  if (!detail) return ''
  if (typeof detail === 'string') return detail
  if (typeof detail === 'object') {
    const record = detail as Record<string, unknown>
    if (typeof record.message === 'string') return record.message
    if (typeof record.detail === 'string') return record.detail
    if (Array.isArray(record.details) && record.details.length > 0) {
      return String(record.details[0])
    }
  }
  return ''
}

export const api = {
  health: () => request<Health>('/health'),

  listPeople: () => request<Person[]>('/people'),
  getProfile: (id: number) => request<PersonProfile>(`/people/${id}/profile`),
  getStyle: (id: number) => request<WritingStyle>(`/people/${id}/style`),
  analyzePerson: (id: number) => request<Record<string, unknown>>(`/people/${id}/analyze`, { method: 'POST' }),
  mergePeople: (fromPersonId: number, toPersonId: number) =>
    request<MergeResult>('/people/merge', {
      method: 'POST',
      body: { from_person_id: fromPersonId, to_person_id: toPersonId },
    }),

  listMemories: (
    params: { personId?: number; memoryType?: string; queryText?: string; status?: string } = {},
  ) =>
    request<Memory[]>('/memories', {
      query: {
        person_id: params.personId,
        memory_type: params.memoryType,
        query_text: params.queryText,
        status: params.status,
      },
    }),
  createMemory: (payload: {
    person_id: number
    content: string
    memory_type: string
    importance?: number
    confidence?: number
  }) => request<Memory>('/memories', { method: 'POST', body: payload }),
  correctMemory: (id: number, correction: string) =>
    request<Memory>(`/memories/${id}/correct`, { method: 'POST', body: { correction } }),
  editMemory: (id: number, content: string) =>
    request<Memory>(`/memories/${id}`, { method: 'PATCH', body: { content } }),
  deleteMemory: (id: number) => request<void>(`/memories/${id}`, { method: 'DELETE' }),

  chat: (payload: {
    message: string
    person_id?: number
    conversation_id?: number
    debug?: boolean
  }) => request<ChatResponse>('/chat', { method: 'POST', body: payload }),

  listProjects: () => request<Project[]>('/projects'),
  getProject: (id: number) => request<ProjectDetail>(`/projects/${id}`),
  createProject: (payload: ProjectCreatePayload) =>
    request<Project>('/projects', { method: 'POST', body: payload }),
  deleteProject: (id: number) => request<void>(`/projects/${id}`, { method: 'DELETE' }),
  listProjectPeople: (projectId: number) =>
    request<Person[]>(`/projects/${projectId}/people`),
  listProjectConversations: (projectId: number) =>
    request<Conversation[]>(`/projects/${projectId}/conversations`),
  listProjectMemories: (
    projectId: number,
    params: {
      personId?: number
      memoryType?: string
      queryText?: string
      status?: string
      limit?: number
    } = {},
  ) =>
    request<Memory[]>(`/projects/${projectId}/memories`, {
      query: {
        person_id: params.personId,
        memory_type: params.memoryType,
        query_text: params.queryText,
        status: params.status,
        limit: params.limit ?? 100,
      },
    }),
  getMemoryVersions: (memoryId: number) =>
    request<MemoryVersion[]>(`/memories/${memoryId}/versions`),

  voiceStatus: () => request<VoiceStatus>('/voice/status'),

  listConversations: () => request<Conversation[]>('/conversations'),
  getConversation: (id: number) => request<Conversation>(`/conversations/${id}`),
  deleteConversation: (id: number) =>
    request<ConversationDeleteResult>(`/conversations/${id}`, { method: 'DELETE' }),
  listMessages: (params: { conversationId?: number; personId?: number; limit?: number } = {}) =>
    request<MessageRecord[]>('/messages', {
      query: {
        conversation_id: params.conversationId,
        person_id: params.personId,
        limit: params.limit ?? 500,
      },
    }),
  getMessage: (id: number) => request<MessageRecord>(`/messages/${id}`),
  deleteMessage: (id: number) => request<void>(`/messages/${id}`, { method: 'DELETE' }),

  getSettings: () => request<AppSettings>('/settings'),

  importJson: (payload: unknown) =>
    request<ImportResult>('/import/json', { method: 'POST', body: payload }),
  importCsv: (file: File, person: string, consentConfirmed: boolean) => {
    const form = new FormData()
    form.append('file', file)
    form.append('person', person)
    form.append('consent_confirmed', String(consentConfirmed))
    return request<ImportResult>('/import/csv', { method: 'POST', formData: form })
  },
  importPreview: (file: File, person: string = '') => {
    const form = new FormData()
    form.append('file', file)
    form.append('person', person)
    return request<ImportPreview>('/import/preview', { method: 'POST', formData: form })
  },
  importTxt: (file: File, person: string, consentConfirmed: boolean, title?: string) => {
    const form = new FormData()
    form.append('file', file)
    form.append('person', person)
    form.append('consent_confirmed', String(consentConfirmed))
    if (title) form.append('title', title)
    return request<ImportResult>('/import/txt', { method: 'POST', formData: form })
  },
  importZip: (file: File, person: string, consentConfirmed: boolean, title?: string) => {
    const form = new FormData()
    form.append('file', file)
    form.append('person', person)
    form.append('consent_confirmed', String(consentConfirmed))
    if (title) form.append('title', title)
    return request<ImportResult>('/import/zip', { method: 'POST', formData: form })
  },
}

export const API_BASE_URL = API_BASE
