import { useState, useRef, useEffect, useCallback } from "react";
import {
  Person,
  Conversation,
  MessageRecord,
  ChatTurn,
  ChatResponse,
} from "../types";
import { api } from "../services/api";
import { MessageBubble } from "./MessageBubble";

type Props = {
  persons: Person[];
  selectedPersonId: number | null;
  onSelectPerson: (id: number | null) => void;
  showMemorySources: boolean;
  debugRetrieval: boolean;
};

export function ChatWindow({
  persons,
  selectedPersonId,
  onSelectPerson,
  showMemorySources,
  debugRetrieval,
}: Props) {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<
    number | null
  >(null);
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  const transcriptRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const epochRef = useRef(0);

  const person = persons.find((p) => p.id === selectedPersonId) ?? null;

  // ── load conversations ───────────────────────────────────────────────
  const loadConversations = useCallback(async () => {
    try {
      const data = await api.listConversations();
      setConversations(data);
    } catch (err: any) {
      setError(err?.message ?? "Failed to load conversations");
    }
  }, []);

  useEffect(() => {
    loadConversations();
  }, [loadConversations]);

  // ── load messages when active conversation changes ────────────────────
  useEffect(() => {
    if (activeConversationId === null) {
      setTurns([]);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const msgs: MessageRecord[] = await api.listMessages({
          conversationId: activeConversationId,
        });
        if (cancelled) return;
        const mapped: ChatTurn[] = msgs.map((m) => ({
          id: m.id,
          role: m.sender === "user" ? "user" : "assistant",
          content: m.content,
          at: m.timestamp ? new Date(m.timestamp).getTime() : undefined,
        }));
        setTurns(mapped);
      } catch (err: any) {
        if (!cancelled) setError(err?.message ?? "Failed to load messages");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [activeConversationId]);

  // ── auto‑scroll ──────────────────────────────────────────────────────
  useEffect(() => {
    const el = transcriptRef.current;
    if (el) {
      requestAnimationFrame(() => {
        el.scrollTop = el.scrollHeight;
      });
    }
  }, [turns, sending]);

  // ── auto‑grow textarea ───────────────────────────────────────────────
  const autoGrow = useCallback(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = "42px";
    ta.style.height = Math.min(ta.scrollHeight, 160) + "px";
  }, []);

  useEffect(() => {
    autoGrow();
  }, [input, autoGrow]);

  // ── person change → bump epoch, clear active conversation ────────────
  useEffect(() => {
    epochRef.current += 1;
    setActiveConversationId(null);
    setTurns([]);
    setInput("");
    setError(null);
    setNotice(null);
    setDeletingId(null);
  }, [selectedPersonId]);

  // ── send ─────────────────────────────────────────────────────────────
  const handleSend = useCallback(async () => {
    const text = input.trim();
    if (!text || sending) return;
    if (!selectedPersonId) {
      setError("Select a person first");
      return;
    }

    const myEpoch = epochRef.current;
    setSending(true);
    setError(null);
    setNotice(null);
    setInput("");

    const userTurn: ChatTurn = {
      id: Date.now(),
      role: "user",
      content: text,
      at: Date.now(),
    };
    setTurns((prev) => [...prev, userTurn]);

    try {
      const resp: ChatResponse = await api.chat({
        message: text,
        person_id: selectedPersonId,
        conversation_id: activeConversationId ?? undefined,
        debug: debugRetrieval,
      });

      if (epochRef.current !== myEpoch) return;

      if (!activeConversationId && resp.conversation_id) {
        setActiveConversationId(resp.conversation_id);
        loadConversations();
      }

      const assistantTurn: ChatTurn = {
        id: Date.now() + 1,
        role: "assistant",
        content: resp.reply,
        at: Date.now(),
        confidence: resp.confidence,
        sources: resp.show_memory_sources ? resp.sources : undefined,
        learned: resp.learned,
        debug: resp.debug,
        memoryIndicator: resp.memory_indicator,
      };
      setTurns((prev) => [...prev, assistantTurn]);
    } catch (err: any) {
      if (epochRef.current !== myEpoch) return;
      setError(err?.message ?? "Failed to get response");
      setTurns((prev) => prev.filter((t) => t.id !== userTurn.id));
      setInput(text);
    } finally {
      if (epochRef.current === myEpoch) setSending(false);
    }
  }, [
    input,
    sending,
    selectedPersonId,
    activeConversationId,
    debugRetrieval,
    loadConversations,
  ]);

  // ── delete conversation ──────────────────────────────────────────────
  const handleDelete = useCallback(
    async (id: number) => {
      if (deletingId !== null) return;
      setDeletingId(id);
      try {
        await api.deleteConversation(id);
        setConversations((prev) => prev.filter((c) => c.id !== id));
        if (activeConversationId === id) {
          setActiveConversationId(null);
          setTurns([]);
        }
        setNotice("Conversation deleted");
      } catch (err: any) {
        setError(err?.message ?? "Failed to delete conversation");
      } finally {
        setDeletingId(null);
      }
    },
    [deletingId, activeConversationId],
  );

  // ── key handler for textarea ─────────────────────────────────────────
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend],
  );

  // ── derived values ───────────────────────────────────────────────────
  const activeConversation = conversations.find(
    (c) => c.id === activeConversationId,
  );

  const sortedConversations = [...conversations].sort(
    (a, b) =>
      new Date(b.started_at ?? 0).getTime() -
      new Date(a.started_at ?? 0).getTime(),
  );

  const lastDate = sortedConversations[0]?.started_at
    ? new Date(sortedConversations[0].started_at).toLocaleDateString()
    : "never";

  const providerAvailable =
    selectedPersonId !== null || activeConversationId !== null;

  // ── render ───────────────────────────────────────────────────────────
  return (
    <div className="chat-layout">
      {/* ── Conversation Rail ───────────────────────────────────────── */}
      <aside className="conversation-rail">
        <div className="rail-head">
          <span>Conversations</span>
          <button
            className="ghost"
            onClick={() => {
              setActiveConversationId(null);
              setTurns([]);
            }}
          >
            + New
          </button>
        </div>

        <div className="rail-summary">
          {conversations.length} conversations · last {lastDate}
        </div>

        <div className="conversation-list">
          {activeConversationId === null && selectedPersonId !== null && (
            <button
              className="active-row active"
              onClick={() => {
                setActiveConversationId(null);
                setTurns([]);
              }}
            >
              <div className="conv-title">New conversation</div>
            </button>
          )}

          {sortedConversations.map((c) => (
            <div
              key={c.id}
              className={`conv-row${c.id === activeConversationId ? " active-row active" : ""}`}
            >
              <button
                className="conv-row-btn"
                onClick={() => {
                  setActiveConversationId(c.id);
                  setTurns([]);
                }}
              >
                <div className="conv-title">{c.title || `Conversation ${c.id}`}</div>
                <div className="conv-meta">
                  <span>{c.message_count} msgs</span>
                  <span>{c.source}</span>
                  <span>
                    {c.started_at
                      ? new Date(c.started_at).toLocaleDateString()
                      : "—"}
                  </span>
                </div>
              </button>
              <button
                className="conv-delete danger"
                title="Delete conversation"
                disabled={deletingId === c.id}
                onClick={(e) => {
                  e.stopPropagation();
                  handleDelete(c.id);
                }}
              >
                ×
              </button>
            </div>
          ))}

          {conversations.length === 0 && selectedPersonId !== null && (
            <div className="conv-empty">No conversations yet</div>
          )}
        </div>
      </aside>

      {/* ── Chat Window ─────────────────────────────────────────────── */}
      <main className="chat-window">
        <div className="panel-head">
          <div className="head-title">
            Chat with {person?.name ?? "…"}
          </div>
          <div className="head-sub">
            <select
              value={selectedPersonId ?? ""}
              onChange={(e) => {
                const v = e.target.value;
                onSelectPerson(v ? Number(v) : null);
              }}
            >
              <option value="">Select person…</option>
              {persons.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
            {activeConversation && (
              <span className="head-conv">
                #{activeConversation.id} · {activeConversation.title || "Untitled"}
              </span>
            )}
          </div>
        </div>

        {/* banners */}
        {error && (
          <div className="error" onClick={() => setError(null)}>
            {error}
          </div>
        )}
        {notice && (
          <div className="notice" onClick={() => setNotice(null)}>
            {notice}
          </div>
        )}

        {/* transcript */}
        <div className="transcript" ref={transcriptRef}>
          {turns.length === 0 && !sending && (
            <div className="empty-state">
              {activeConversationId === null
                ? selectedPersonId === null
                  ? "Select a person to start chatting."
                  : "Start a new conversation above."
                : "No messages yet."}
            </div>
          )}

          {turns.map((t) => (
            <MessageBubble
              key={t.id}
              turn={t}
              showMemorySources={showMemorySources}
            />
          ))}

          {sending && (
            <div className="typing-indicator">
              <span className="typing-dot" />
              <span className="typing-dot" />
              <span className="typing-dot" />
            </div>
          )}
        </div>

        {/* composer */}
        <div className="composer">
          <textarea
            ref={textareaRef}
            rows={1}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              providerAvailable
                ? "Type a message…"
                : "Select a person or start a new conversation…"
            }
            disabled={!providerAvailable}
          />
          <button
            className="send-btn"
            disabled={!input.trim() || sending || !providerAvailable}
            onClick={handleSend}
          >
            {sending ? "…" : "→"}
          </button>
        </div>
      </main>
    </div>
  );
}
