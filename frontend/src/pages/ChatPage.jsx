import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Loader2, Send, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import * as api from '../api/client.js'
import { ChatHistorySidebar } from '../components/ChatHistorySidebar.jsx'
import { ChatMessage } from '../components/ChatMessage.jsx'
import { PipelineDebugModal } from '../components/PipelineDebugModal.jsx'
import { Navbar } from '../components/Navbar.jsx'
import { NeonPageShell } from '../components/NeonPageShell.jsx'
import { ThemedPageBackdrop } from '../components/ThemedPageBackdrop.jsx'
import { useTheme } from '../context/ThemeContext.jsx'
import { getApiErrorMessage, isNetworkError } from '../utils/apiError.js'
import bannerLight from '../assets/banner.png'
import bannerDark from '../assets/banner2.png'

const EXAMPLE_PROMPTS = [
  'Neo-noir thrillers with unreliable narrators and twist endings',
  'Character-driven dramas from the 2010s with bittersweet endings',
  'Visually bold sci-fi that still feels grounded and human',
]

const MORE_RECOMMENDATIONS_PROMPT =
  'Show me more recommendations for the same request. Pick different movies — do not repeat any films you have already suggested in this conversation.'

function newSessionId() {
  return crypto.randomUUID()
}

function mapHistoryToMessages(rows) {
  return (rows || []).map((row) => ({
    id: String(row.id),
    role: row.role,
    content: row.content,
    recommendations: row.role === 'assistant' ? row.recommendations || [] : null,
    debug: row.role === 'assistant' ? row.debug ?? null : null,
  }))
}

export function ChatPage() {
  const { theme } = useTheme()
  const inputRef = useRef(null)
  const [sessionId, setSessionId] = useState(() => newSessionId())
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [debugModalOpen, setDebugModalOpen] = useState(false)
  const [selectedDebug, setSelectedDebug] = useState(null)
  const [sidebarOpen, setSidebarOpen] = useState(() =>
    typeof window !== 'undefined' ? window.matchMedia('(min-width: 1024px)').matches : false
  )
  const [sessions, setSessions] = useState([])
  const [sessionsLoading, setSessionsLoading] = useState(true)
  const [historyLoading, setHistoryLoading] = useState(false)
  const [deletingChatId, setDeletingChatId] = useState(null)

  const canSend = input.trim().length > 0 && !sending

  const lastAssistantWithRecsId = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i -= 1) {
      const msg = messages[i]
      if (msg.role === 'assistant' && msg.recommendations?.length) return msg.id
    }
    return null
  }, [messages])

  const refreshSessions = useCallback(async () => {
    try {
      const res = await api.getChats()
      setSessions(res.chats || [])
    } catch (e) {
      if (!isNetworkError(e)) {
        toast.error(getApiErrorMessage(e, 'Could not load chat history.'))
      }
    } finally {
      setSessionsLoading(false)
    }
  }, [])

  useEffect(() => {
    refreshSessions()
  }, [refreshSessions])

  const loadSession = useCallback(
    async (id) => {
      if (id === sessionId && messages.length > 0) return
      setHistoryLoading(true)
      setDebugModalOpen(false)
      setSelectedDebug(null)
      try {
        const res = await api.getChat(id)
        setSessionId(res.id)
        setMessages(mapHistoryToMessages(res.messages))
        if (typeof window !== 'undefined' && window.matchMedia('(max-width: 1023px)').matches) {
          setSidebarOpen(false)
        }
      } catch (e) {
        toast.error(getApiErrorMessage(e, 'Could not load this chat.'))
      } finally {
        setHistoryLoading(false)
      }
    },
    [sessionId, messages.length]
  )

  const handleMarkWatched = useCallback(async (movieId) => {
    const fromMessage = messages
      .flatMap((m) => m.recommendations || [])
      .find((r) => r.movie_id === movieId)
    if (!fromMessage) return
    try {
      await api.addWatched(
        fromMessage.movie_id,
        fromMessage.title,
        fromMessage.year,
        fromMessage.genres,
        null
      )
      toast.success('Added to your watched list.')
    } catch (e) {
      toast.error(getApiErrorMessage(e, 'Could not add to watched list.'))
    }
  }, [messages])

  const send = useCallback(
    async (text, { silent = false } = {}) => {
      const trimmed = text.trim()
      if (!trimmed || sending) return
      setSending(true)
      const userEntry = silent
        ? null
        : {
            id: crypto.randomUUID(),
            role: 'user',
            content: trimmed,
            recommendations: null,
          }
      if (userEntry) {
        setMessages((m) => [...m, userEntry])
        setInput('')
      }

      const appendAssistant = (res) => {
        setMessages((m) => [
          ...m,
          {
            id: crypto.randomUUID(),
            role: 'assistant',
            content: res.response_text,
            recommendations: res.recommendations || [],
            debug: res.debug ?? null,
          },
        ])
      }

      try {
        const res = await api.sendMessage(trimmed, sessionId, { silent })
        appendAssistant(res)
        refreshSessions()
      } catch (e) {
        const msg = getApiErrorMessage(e, 'Something went wrong.')
        toast.error(isNetworkError(e) ? 'Cannot reach the API. Is the backend running on port 8000?' : msg)
        if (userEntry) {
          setMessages((m) => m.filter((x) => x.id !== userEntry.id))
        }
      } finally {
        setSending(false)
      }
    },
    [sending, sessionId, refreshSessions]
  )

  const handleMore = useCallback(() => {
    send(MORE_RECOMMENDATIONS_PROMPT, { silent: true })
  }, [send])

  const onSubmit = (e) => {
    e.preventDefault()
    send(input)
  }

  const handleDeleteChat = useCallback(
    async (chatId) => {
      setDeletingChatId(chatId)
      try {
        await api.deleteChat(chatId)
        setSessions((list) => list.filter((s) => (s.id ?? s.session_id) !== chatId))
        if (chatId === sessionId) {
          const res = await api.createChat()
          setSessionId(res.id)
          setMessages([])
          setSelectedDebug(null)
          setDebugModalOpen(false)
          setInput('')
        }
        refreshSessions()
        toast.success('Chat deleted.')
      } catch (e) {
        toast.error(getApiErrorMessage(e, 'Could not delete chat.'))
      } finally {
        setDeletingChatId(null)
      }
    },
    [sessionId, refreshSessions]
  )

  const newChat = useCallback(async () => {
    try {
      const res = await api.createChat()
      setSessionId(res.id)
      setMessages([])
      setSelectedDebug(null)
      setDebugModalOpen(false)
      setInput('')
      refreshSessions()
      if (typeof window !== 'undefined' && window.matchMedia('(max-width: 1023px)').matches) {
        setSidebarOpen(false)
      }
    } catch (e) {
      toast.error(getApiErrorMessage(e, 'Could not start a new chat.'))
    }
  }, [refreshSessions])

  const isEmpty = messages.length === 0 && !historyLoading

  return (
    <NeonPageShell className="min-h-screen flex flex-col">
      <ThemedPageBackdrop page="chat" />
      <Navbar />
      <div className="relative z-[1] flex flex-1 min-h-0 w-full max-w-[1400px] mx-auto">
        <ChatHistorySidebar
          open={sidebarOpen}
          onToggle={() => setSidebarOpen((v) => !v)}
          sessions={sessions}
          activeSessionId={sessionId}
          loading={sessionsLoading}
          onSelectSession={loadSession}
          onNewChat={newChat}
        />

        <main className="flex-1 flex flex-col min-w-0 px-4 pb-32 pt-6 animate-fade-in">
          <div
            className={
              isEmpty
                ? 'flex flex-wrap items-center justify-between gap-3 mb-6'
                : 'flex flex-wrap items-center justify-between gap-3 mb-4'
            }
          >
            {isEmpty ? (
              <div className="min-w-0 flex-1">
                <h1 className="text-lg font-semibold text-[var(--color-fg)] tracking-tight transition-colors duration-300">
                  Recommendations board
                </h1>
                <p className="text-sm text-[var(--color-muted)]">
                  Conversational retrieval — each reply may include grounded movie cards below the text.
                </p>
              </div>
            ) : (
              <div className="flex items-center gap-2 min-w-0">
                {!sidebarOpen ? (
                  <button
                    type="button"
                    onClick={() => setSidebarOpen(true)}
                    className="hidden lg:inline-flex rounded-full border border-[var(--color-border)] bg-[var(--color-chip-bg)] px-3 py-1.5 text-xs font-medium text-[var(--color-muted)] hover:text-[var(--color-fg)] hover:border-amber-600/35 transition-all duration-200"
                  >
                    History
                  </button>
                ) : null}
              </div>
            )}
            <div className="flex items-center gap-2 shrink-0">
              <button
                type="button"
                onClick={newChat}
                className="btn-toolbar rounded-full border border-[var(--color-border)] bg-[var(--color-chip-bg)] px-4 py-2 text-sm font-medium text-[var(--color-fg)] hover:border-amber-600/40 hover:bg-[var(--color-surface-elevated)] shadow-sm transition-all duration-200 hover:scale-[1.02] active:scale-[0.98]"
              >
                New chat
              </button>
              {!isEmpty ? (
                <button
                  type="button"
                  onClick={() => handleDeleteChat(sessionId)}
                  disabled={!sessionId || deletingChatId === sessionId}
                  className="btn-toolbar rounded-full border border-[var(--color-border)] bg-[var(--color-chip-bg)] p-2 text-[var(--color-muted)] hover:text-red-600 hover:border-red-500/35 hover:bg-red-500/10 shadow-sm transition-all duration-200 disabled:opacity-40 disabled:pointer-events-none"
                  aria-label="Delete this chat"
                  title="Delete this chat"
                >
                  <Trash2 size={18} aria-hidden />
                </button>
              ) : null}
            </div>
          </div>

          {isEmpty ? (
            <section
              className={`chat-hero-banner relative rounded-[1.75rem] overflow-hidden mb-10 min-h-[300px] border transition-transform duration-500 hover:scale-[1.005] ${
                theme === 'light'
                  ? 'border-[var(--color-border)] shadow-xl shadow-stone-900/15 ring-1 ring-stone-900/10'
                  : theme === 'neon'
                    ? 'chat-hero-banner--neon border-violet-700/50 shadow-xl shadow-[#07050F]/60 ring-1 ring-violet-400/35'
                    : 'border-[var(--color-border)] shadow-xl shadow-black/50 ring-1 ring-white/10'
              }`}
            >
              <img
                src={
                  theme === 'light'
                    ? bannerLight
                    : bannerDark
                }
                alt=""
                className="chat-hero-banner__image absolute inset-0 h-full w-full object-cover object-center"
              />
            </section>
          ) : null}

          {isEmpty ? (
            <div className="mb-10">
              <p className="text-xs uppercase tracking-[0.15em] text-[var(--color-muted)] mb-3">
                Try a starter prompt
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 stagger-children">
                {EXAMPLE_PROMPTS.map((prompt) => (
                  <button
                    key={prompt}
                    type="button"
                    onClick={() => {
                      setInput(prompt)
                      inputRef.current?.focus()
                    }}
                    className="interactive-chip text-left rounded-2xl border border-[var(--color-chip-border)] bg-[var(--color-chip-bg)] px-4 py-3 text-sm text-[var(--color-fg-secondary)] hover:border-amber-600/35 h-full"
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            </div>
          ) : null}

          <div className="flex-1 space-y-0 min-h-[40vh]">
            {historyLoading ? (
              <div className="flex items-center gap-2 text-[var(--color-muted)] text-sm py-3 animate-fade-in">
                <Loader2 className="animate-spin text-amber-500/90" size={18} aria-hidden />
                Loading conversation…
              </div>
            ) : null}
            {messages.map((msg) => (
              <ChatMessage
                key={msg.id}
                role={msg.role}
                content={msg.content}
                recommendations={msg.recommendations}
                debug={msg.debug}
                onMarkWatched={handleMarkWatched}
                onViewDebug={(debug) => {
                  setSelectedDebug(debug)
                  setDebugModalOpen(true)
                }}
                showMore={msg.id === lastAssistantWithRecsId}
                onMore={handleMore}
                moreDisabled={sending}
              />
            ))}
            {sending ? (
              <div className="flex items-center gap-2 text-[var(--color-muted)] text-sm py-3 animate-fade-in">
                <Loader2 className="animate-spin text-amber-500/90" size={18} aria-hidden />
                Thinking with your library and the corpus…
              </div>
            ) : null}
          </div>

        </main>
      </div>

      <PipelineDebugModal
        isOpen={debugModalOpen}
        onClose={() => {
          setDebugModalOpen(false)
          setSelectedDebug(null)
        }}
        debug={selectedDebug}
      />

      <div className="fixed bottom-0 left-0 right-0 border-t border-[var(--color-border-subtle)] bg-[var(--color-bg)]/95 backdrop-blur-md z-40">
        <form
          onSubmit={onSubmit}
          className="max-w-[1100px] mx-auto px-4 py-3 flex flex-row items-center gap-3"
        >
          <label className="flex-1 min-w-0 flex">
            <span className="sr-only">Message</span>
            <textarea
              ref={inputRef}
              rows={1}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  if (canSend) send(input)
                }
              }}
              placeholder="Describe a mood, a reference film, or a constraint…"
              className="w-full resize-y rounded-2xl bg-[var(--color-surface)] border border-[var(--color-border)] px-4 py-3.5 text-sm leading-snug text-[var(--color-fg)] placeholder:text-[var(--color-muted)] outline-none transition-all duration-200 focus:ring-2 focus:ring-amber-500/35 focus:border-amber-600/35 min-h-[52px] max-h-40"
            />
          </label>
          <button
            type="submit"
            disabled={!canSend}
            className="shrink-0 h-[52px] w-[52px] rounded-2xl btn-neon-accent flex items-center justify-center p-0 disabled:opacity-40 disabled:shadow-none disabled:transform-none disabled:hover:transform-none"
            aria-label="Send"
          >
            <Send size={20} className="transition-transform duration-200" />
          </button>
        </form>
      </div>
    </NeonPageShell>
  )
}
