import { useCallback, useMemo, useRef, useState } from 'react'
import { Loader2, Send } from 'lucide-react'
import * as api from '../api/client.js'
import { mockChat } from '../api/mockBackend.js'
import { ChatMessage } from '../components/ChatMessage.jsx'
import { Navbar } from '../components/Navbar.jsx'

const EXAMPLE_PROMPTS = [
  'Neo-noir thrillers with unreliable narrators and twist endings',
  'Character-driven dramas from the 2010s with bittersweet endings',
  'Visually bold sci-fi that still feels grounded and human',
]

function newSessionId() {
  return crypto.randomUUID()
}

export function ChatPage() {
  const inputRef = useRef(null)
  const [sessionId, setSessionId] = useState(() => newSessionId())
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState('')
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
    } catch (e) {
      setError(e.body?.detail || e.message || 'Could not add to watched list.')
    }
  }, [messages])

  const send = useCallback(
    async (text) => {
      const trimmed = text.trim()
      if (!trimmed || sending) return
      setError('')
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
        if (api.USE_MOCK) {
          const res = await mockChat(trimmed, sessionId)
          appendAssistant(res)
        } else {
          try {
            const res = await api.sendMessage(trimmed, sessionId)
            appendAssistant(res)
          } catch {
            const res = await mockChat(trimmed, sessionId)
            appendAssistant(res)
            setError('API unavailable — showing offline mock reply.')
          }
        }
      } catch (e) {
        setError(e.body?.detail || e.message || 'Something went wrong.')
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
      backgroundImage:
        'linear-gradient(145deg, rgba(9,9,11,.88), rgba(120,53,15,.42)), url(https://images.unsplash.com/photo-1536440136628-849c177e76a1?auto=format&fit=crop&w=1600&q=80)',
      backgroundSize: 'cover',
      backgroundPosition: 'center',
    }),
    []
  )

  function newChat() {
    setSessionId(newSessionId())
    setMessages([])
    setLastDebug(null)
    setShowDebug(false)
    setError('')
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
              <h1 className="text-lg font-semibold text-white tracking-tight transition-colors duration-300">
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
            className="rounded-full border border-amber-500/35 bg-zinc-900/40 px-4 py-2 text-sm font-medium text-stone-100 hover:bg-amber-950/35 hover:border-amber-500/50 shadow-sm transition-all duration-200 hover:scale-[1.02] active:scale-[0.98]"
          >
            New chat
          </button>
        </div>

        {messages.length === 0 ? (
          <section
            className="relative rounded-[1.75rem] overflow-hidden mb-10 min-h-[220px] border border-white/[0.08] shadow-lg shadow-black/40 ring-1 ring-amber-900/25 transition-transform duration-500 hover:scale-[1.003]"
            style={heroStyle}
          >
            <div className="absolute inset-0 flex flex-col justify-end p-6 sm:p-8">
              <p className="text-xs uppercase tracking-[0.2em] text-amber-200/85 mb-1 animate-fade-in-up">
                Featured
              </p>
              <h2 className="text-2xl sm:text-3xl font-bold text-white mb-3 drop-shadow-lg">
                Stories worth the late night
              </h2>
              <p className="text-sm text-white/90 max-w-lg">
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
                  className="interactive-chip text-left rounded-2xl border border-white/[0.08] bg-zinc-900/50 px-4 py-3 text-sm text-zinc-200 hover:border-amber-500/30 hover:bg-amber-950/20 h-full"
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

        {error ? (
          <div
            className={
              error.includes('offline mock')
                ? 'mb-4 rounded-xl bg-amber-950/35 border border-amber-700/35 px-3 py-2 text-sm text-amber-100/95 animate-fade-in'
                : 'mb-4 rounded-xl bg-red-500/15 border border-red-500/30 px-3 py-2 text-sm text-red-200 animate-fade-in'
            }
          >
            {error}
          </div>
        ) : null}

        {lastDebug ? (
          <div className="mt-4 border-t border-white/10 pt-4">
            <button
              type="button"
              onClick={() => setShowDebug((v) => !v)}
              className="text-xs font-medium text-[var(--color-muted)] hover:text-amber-200/90 transition-colors duration-200"
            >
              {showDebug ? 'Hide' : 'Show'} pipeline debug
            </button>
            {showDebug ? (
              <pre className="mt-2 text-[11px] leading-relaxed text-zinc-400 overflow-x-auto rounded-xl bg-zinc-950/90 p-3 border border-white/[0.07] max-h-64 overflow-y-auto animate-fade-in-up">
                {JSON.stringify(lastDebug, null, 2)}
              </pre>
            ) : null}
          </div>
        ) : null}
      </main>

      <div className="fixed bottom-0 left-0 right-0 border-t border-white/[0.08] bg-[var(--color-bg)]/95 backdrop-blur-md z-40">
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
              className="w-full resize-y rounded-2xl bg-[var(--color-surface)] border border-white/[0.08] px-4 py-3.5 text-sm leading-snug text-zinc-100 placeholder:text-zinc-500 outline-none transition-all duration-200 focus:ring-2 focus:ring-amber-500/35 focus:border-amber-600/35 min-h-[52px] max-h-40"
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
