import { useCallback, useMemo, useRef, useState } from 'react'
import { Loader2, Send } from 'lucide-react'
import { toast } from 'sonner'
import * as api from '../api/client.js'
import { ChatMessage } from '../components/ChatMessage.jsx'
import { Navbar } from '../components/Navbar.jsx'
import { useTheme } from '../context/ThemeContext.jsx'
import { getApiErrorMessage, isNetworkError } from '../utils/apiError.js'

const EXAMPLE_PROMPTS = [
  'Neo-noir thrillers with unreliable narrators and twist endings',
  'Character-driven dramas from the 2010s with bittersweet endings',
  'Visually bold sci-fi that still feels grounded and human',
]

function newSessionId() {
  return crypto.randomUUID()
}

export function ChatPage() {
  const { isLight } = useTheme()
  const inputRef = useRef(null)
  const [sessionId, setSessionId] = useState(() => newSessionId())
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [showDebug, setShowDebug] = useState(false)
  const [lastDebug, setLastDebug] = useState(null)

  const canSend = input.trim().length > 0 && !sending

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
    async (text) => {
      const trimmed = text.trim()
      if (!trimmed || sending) return
      setSending(true)
      const userEntry = {
        id: crypto.randomUUID(),
        role: 'user',
        content: trimmed,
        recommendations: null,
      }
      setMessages((m) => [...m, userEntry])
      setInput('')

      const appendAssistant = (res) => {
        setLastDebug(res.debug ?? null)
        setMessages((m) => [
          ...m,
          {
            id: crypto.randomUUID(),
            role: 'assistant',
            content: res.response_text,
            recommendations: res.recommendations || [],
          },
        ])
      }

      try {
        const res = await api.sendMessage(trimmed, sessionId)
        appendAssistant(res)
      } catch (e) {
        const msg = getApiErrorMessage(e, 'Something went wrong.')
        toast.error(isNetworkError(e) ? 'Cannot reach the API. Is the backend running on port 8000?' : msg)
        setMessages((m) => m.filter((x) => x.id !== userEntry.id))
      } finally {
        setSending(false)
      }
    },
    [sending, sessionId]
  )

  const onSubmit = (e) => {
    e.preventDefault()
    send(input)
  }

  const heroStyle = useMemo(
    () => ({
      backgroundImage: isLight
        ? 'linear-gradient(145deg, rgba(255,252,248,.72), rgba(254,129,090,.12)), url(https://images.unsplash.com/photo-1631702825172-a9a848c473ad?auto=format&fit=crop&w=1600&q=80)'
        : 'linear-gradient(145deg, rgba(9,9,11,.88), rgba(120,53,15,.42)), url(https://images.unsplash.com/photo-1536440136628-849c177e76a1?auto=format&fit=crop&w=1600&q=80)',
      backgroundSize: 'cover',
      backgroundPosition: 'center',
    }),
    [isLight]
  )

  function newChat() {
    setSessionId(newSessionId())
    setMessages([])
    setLastDebug(null)
    setShowDebug(false)
    setInput('')
  }

  return (
    <div className="min-h-screen flex flex-col bg-[var(--color-bg)]">
      <Navbar />
      <main className="flex-1 flex flex-col max-w-[1100px] w-full mx-auto px-4 pb-32 pt-6 animate-fade-in">
        <div
          className={
            messages.length === 0
              ? 'flex flex-wrap items-center justify-between gap-3 mb-6'
              : 'flex justify-end mb-4'
          }
        >
          {messages.length === 0 ? (
            <div>
              <h1 className="text-lg font-semibold text-[var(--color-fg)] tracking-tight transition-colors duration-300">
                Recommendations board
              </h1>
              <p className="text-sm text-[var(--color-muted)]">
                Conversational retrieval — each reply may include grounded movie cards below the text.
              </p>
            </div>
          ) : null}
          <button
            type="button"
            onClick={newChat}
            className="rounded-full border border-[var(--color-border)] bg-[var(--color-chip-bg)] px-4 py-2 text-sm font-medium text-[var(--color-fg)] hover:border-amber-600/40 hover:bg-[var(--color-surface-elevated)] shadow-sm transition-all duration-200 hover:scale-[1.02] active:scale-[0.98]"
          >
            New chat
          </button>
        </div>

        {messages.length === 0 ? (
          <section
            className={`relative  rounded-[1.75rem] overflow-hidden mb-10 min-h-[220px] border border-[var(--color-border)] transition-transform duration-500 hover:scale-[1.003] ${
              isLight ? 'shadow-lg shadow-stone-900/10 ring-1 ring-amber-200/50' : 'shadow-lg shadow-black/40 ring-1 ring-amber-900/25'
            }`}
            style={heroStyle}
          >
            <div className="absolute inset-0 flex flex-col justify-end p-6 sm:p-8">
              <p
                className={`text-xs uppercase tracking-[0.2em] mb-1 animate-fade-in-up ${
                  isLight ? 'text-amber-900/75' : 'text-amber-200/85'
                }`}
              >
                Featured
              </p>
              <h2
                className={`text-2xl sm:text-3xl font-bold mb-3 drop-shadow-sm ${
                  isLight ? 'text-stone-900' : 'text-white drop-shadow-lg'
                }`}
              >
                Stories worth the late night
              </h2>
              <p className={`text-sm max-w-lg ${isLight ? 'text-stone-800' : 'text-white/90'}`}>
                Ask naturally — retrieval blends lexical and semantic signals before the model explains choices
                with citations.
              </p>
            </div>
          </section>
        ) : null}

        {messages.length === 0 ? (
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
          {messages.map((msg) => (
            <ChatMessage
              key={msg.id}
              role={msg.role}
              content={msg.content}
              recommendations={msg.recommendations}
              onMarkWatched={handleMarkWatched}
            />
          ))}
          {sending ? (
            <div className="flex items-center gap-2 text-[var(--color-muted)] text-sm py-3 animate-fade-in">
              <Loader2 className="animate-spin text-amber-500/90" size={18} aria-hidden />
              Thinking with your library and the corpus…
            </div>
          ) : null}
        </div>

        {lastDebug ? (
          <div className="mt-4 border-t border-[var(--color-border-subtle)] pt-4">
            <button
              type="button"
              onClick={() => setShowDebug((v) => !v)}
              className="text-xs font-medium text-[var(--color-muted)] hover:text-[var(--color-accent)] transition-colors duration-200"
            >
              {showDebug ? 'Hide' : 'Show'} pipeline debug
            </button>
            {showDebug ? (
              <pre className="mt-2 text-[11px] leading-relaxed text-[var(--color-debug-fg)] overflow-x-auto rounded-xl bg-[var(--color-debug-bg)] p-3 border border-[var(--color-border)] max-h-64 overflow-y-auto animate-fade-in-up">
                {JSON.stringify(lastDebug, null, 2)}
              </pre>
            ) : null}
          </div>
        ) : null}
      </main>

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
    </div>
  )
}
