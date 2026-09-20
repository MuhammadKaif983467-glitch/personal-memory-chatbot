type Person = {
  id: number
  name: string
  relationship: string
  participant_role?: string
  project_id?: number | null
  created_at: string
  updated_at: string
  message_count: number
}

type ProjectParticipant = {
  name: string
  role: string
}

type Project = {
  id: number
  name: string
  user_id: string
  created_at: string
  stats: Record<string, number>
}

type ProjectDetail = Project & {
  participants: Person[]
}

type Fact = {
  value: string
  confidence: number
  source_message_id?: number | null
  source_text?: string
  created_at?: string
}

type Topic = { value: string; confidence: number }

type PersonProfile = {
  person_id: number
  interests: Fact[]
  preferences: Fact[]
  important_facts: Fact[]
  communication_habits: string[]
  topics: Topic[]
  generated_at: string
}

type WritingStyle = {
  person_id: number
  common_words: string[]
  common_phrases: string[]
  emoji_usage: Record<string, unknown>
  sticker_usage: Record<string, unknown>
  average_message_length: number
  average_words_per_message: number
  language_mix: Record<string, number>
  tone: string
  punctuation_style: Record<string, unknown>
  common_greetings: string[]
  common_endings: string[]
  analyzed_at: string
}

type MemoryVersion = {
  id: number
  memory_id: number
  revision: number
  status: string
  content: string
  memory_type: string
  confidence: number
  importance: number
  source_message_id?: number | null
  note: string
  actor: string
  created_at: string
}

type LearnedMemory = {
  outcome: string
  memory_id?: number | null
  person_id?: number | null
  content: string
  memory_type: string
  superseded_memory_id?: number | null
  reason: string
}

type VoiceProvider = {
  id: string
  name: string
  kind: string
  available: boolean
  requires_key: boolean
  error: string
}

type VoiceStatus = {
  enabled: boolean
  stt: VoiceProvider
  tts: VoiceProvider
  message: string
}

type ImportPreviewItem = {
  line: number
  sender: string
  timestamp: string | null
  content: string
  message_type: string
  issue: string
}

type ImportPreview = {
  source: string
  person: string
  file_name: string
  total_records: number
  valid_messages: number
  malformed: number
  empty: number
  preview: ImportPreviewItem[]
  warnings: string[]
  consent_required: boolean
  messages_previewed: number
  participants?: string[]
  platform?: string
  confidence?: number
}

type PaginatedMessages = {
  items: MessageRecord[]
  total: number
  limit: number
  offset: number
}

type ProjectCreatePayload = {
  name: string
  participants: ProjectParticipant[]
}

type ProjectUpdatePayload = {
  name: string
}

type Memory = {
  id: number
  person_id: number
  person_name: string
  content: string
  source_message_id?: number | null
  memory_type: string
  importance: number
  confidence: number
  status: string
  note: string
  created_at: string
  updated_at: string
}

type Confidence = {
  level: string
  score: number
  signals: Record<string, unknown>
}

type MemorySource = {
  memory_id: number
  content: string
  memory_type: string
  confidence: number
  importance: number
  status: string
  source_timestamp?: string | null
}

type Conversation = {
  id: number
  person_id: number
  project_id?: number | null
  title: string
  source: string
  started_at?: string | null
  ended_at?: string | null
  message_count: number
}

type ConversationDeleteResult = {
  conversation_id: number
  messages_deleted: number
  memories_deleted: number
  memories_preserved: number
}

type MessageRecord = {
  id: number
  conversation_id: number
  person_id?: number | null
  sender: string
  content: string
  original_content: string
  timestamp?: string | null
  message_type: string
  is_duplicate: boolean
  is_spam: boolean
  language: string
  metadata: Record<string, unknown>
}

type AppSettings = {
  app_name: string
  app_version: string
  provider: string
  provider_mode: string
  api_key_configured: boolean
  auth_status: string
  chat_key_configured: boolean
  embedding_key_configured: boolean
  split_keys_in_use: boolean
  tts_configured: boolean
  chat_model: string
  embedding_model: string
  embedding_compatible: boolean
  vector_store: string
  show_memory_sources: boolean
  consent_required: boolean
  analyze_on_import: boolean
  memory_min_confidence: number
  retrieval_limit: number
  context_budget_chars: number
  recent_conversation_messages: number
}

type RetrievedMemory = {
  memory_id: number
  content: string
  memory_type: string
  confidence: number
  importance: number
  source_message_id?: number | null
  source_timestamp?: string | null
  similarity: number
  rank: number
}

type ChatDebug = {
  retrieved: RetrievedMemory[]
  context_chars: number
  context_sample: string
}

type ChatResponse = {
  reply: string
  conversation_id: number
  confidence: Confidence
  memory_indicator?: string | null
  show_memory_sources: boolean
  sources: MemorySource[]
  learned?: LearnedMemory[]
  debug?: ChatDebug | null
}

type ImportResult = {
  ok: boolean
  conversation_id?: number | null
  person_id?: number | null
  person_name: string
  conversation_title: string
  total: number
  imported: number
  skipped: number
  removed_empty: number
  removed_duplicates: number
  removed_system: number
  spam_flagged: number
  cleaned: number
  messages_created: number
  errors: string[]
}

type MergeResult = {
  from_person_id: number
  to_person_id: number
  moved_messages: number
  moved_conversations: number
  merged_profiles: boolean
}

type Health = {
  status: string
  app: string
  version: string
  provider: string
  provider_auth_configured: boolean
  chat_auth_configured: boolean
  embedding_auth_configured: boolean
  tts_configured: boolean
  chat_model?: string | null
  embedding_model?: string | null
  embedding_compatible: boolean
  embedding_problems?: string[]
  vector_store: string
  vector_count: number
  counts: Record<string, number>
  counters: Record<string, number>
}

type ChatTurn = {
  id: number
  role: 'user' | 'assistant'
  content: string
  at?: number
  confidence?: Confidence
  sources?: MemorySource[]
  learned?: LearnedMemory[]
  debug?: ChatDebug | null
  memoryIndicator?: string | null
  speakerName?: string
}

export type {
  Person,
  ProjectParticipant,
  Project,
  ProjectDetail,
  ProjectCreatePayload,
  ProjectUpdatePayload,
  Fact,
  Topic,
  PersonProfile,
  WritingStyle,
  Memory,
  Confidence,
  MemorySource,
  RetrievedMemory,
  ChatDebug,
  ChatResponse,
  Conversation,
  ConversationDeleteResult,
  MessageRecord,
  AppSettings,
  ImportResult,
  MergeResult,
  Health,
  ChatTurn,
  MemoryVersion,
  LearnedMemory,
  VoiceProvider,
  VoiceStatus,
  ImportPreviewItem,
  ImportPreview,
  PaginatedMessages,
}
