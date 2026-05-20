import { History, MessageSquarePlus, PanelLeftClose, PanelLeftOpen } from 'lucide-react'

function formatSessionDate(iso) {
  if (!iso) return ''
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return ''
  const now = new Date()
  const sameDay =
    date.getFullYear() === now.getFullYear() &&
    date.getMonth() === now.getMonth() &&
    date.getDate() === now.getDate()
  if (sameDay) {
    return date.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })
  }
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

export function ChatHistorySidebar({
  open,
  onToggle,
  sessions,
  activeSessionId,
  loading,
  onSelectSession,
  onNewChat,
}) {
  return (
    <>
      {open ? (
        <button
          type="button"
          aria-label="Close chat history"
          className="fixed inset-0 z-30 bg-[var(--color-overlay)] backdrop-blur-[2px] lg:hidden animate-fade-in"
          onClick={onToggle}
        />
      ) : null}

      <aside
        className={`
          sidebar-panel fixed lg:sticky top-[57px] lg:top-0 z-40 lg:z-0
          flex flex-col shrink-0 h-[calc(100vh-57px)] lg:h-auto lg:min-h-[calc(100vh-57px)]
          border-r border-[var(--color-border-subtle)]
          transition-[width,transform] duration-300 ease-out
          ${open ? 'w-[min(100%,280px)] translate-x-0' : 'w-0 -translate-x-full lg:translate-x-0 lg:w-12'}
        `}
        aria-hidden={!open}
      >
        <div className={open ? 'flex flex-col h-full overflow-hidden w-full' : 'hidden'}>
          <div className="sidebar-panel-header relative flex items-center justify-between gap-2 px-4 py-3.5 pl-5">
            <div className="min-w-0 flex items-center gap-2.5">
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-[var(--color-sidebar-item)] border border-[var(--color-border-subtle)] text-amber-600/90">
                <History size={15} aria-hidden />
              </span>
              <div className="min-w-0">
                <p className="text-[10px] uppercase tracking-[0.18em] text-[var(--color-muted)]">History</p>
                <p className="text-sm font-semibold text-[var(--color-fg)] truncate tracking-tight">Past chats</p>
              </div>
            </div>
            <button
              type="button"
              onClick={onToggle}
              className="shrink-0 rounded-xl p-2 text-[var(--color-muted)] hover:text-[var(--color-fg)] sidebar-session-item border border-transparent hover:border-[var(--color-border)] transition-all duration-200"
              aria-label="Close sidebar"
            >
              <PanelLeftClose size={18} />
            </button>
          </div>

          <div className="p-3 border-b border-[var(--color-border-subtle)]/80">
            <button
              type="button"
              onClick={onNewChat}
              className="interactive-chip btn-toolbar w-full flex items-center justify-center gap-2 rounded-2xl border border-[var(--color-border)] bg-[var(--color-sidebar-item-hover)] px-3 py-2.5 text-sm font-medium text-[var(--color-fg)] hover:border-amber-600/25"
            >
              <MessageSquarePlus size={16} className="text-[var(--color-accent)] shrink-0" />
              New chat
            </button>
          </div>

          <div className="flex-1 overflow-y-auto px-2.5 py-3">
            {loading ? (
              <p className="px-2 py-3 text-sm text-[var(--color-muted)] animate-pulse">Loading chats…</p>
            ) : sessions.length === 0 ? (
              <p className="px-3 py-4 text-sm text-[var(--color-muted)] leading-relaxed rounded-2xl border border-dashed border-[var(--color-border-subtle)] bg-[var(--color-sidebar-item)]/60">
                No past chats yet. Start a conversation and it will appear here.
              </p>
            ) : (
              <ul className="space-y-1.5 stagger-children">
                {sessions.map((session) => {
                  const chatId = session.id ?? session.session_id
                  const isActive = chatId === activeSessionId
                  return (
                    <li key={chatId}>
                      <button
                        type="button"
                        onClick={() => onSelectSession(chatId)}
                        className={`interactive-chip sidebar-session-item w-full text-left rounded-xl border px-3 py-2.5 transition-all duration-200 ${
                          isActive
                            ? 'sidebar-session-active'
                            : 'border-transparent hover:border-[var(--color-border-subtle)]'
                        }`}
                      >
                        <span className="block text-sm font-medium text-[var(--color-fg)] line-clamp-2 leading-snug">
                          {session.preview || session.title || 'New conversation'}
                        </span>
                        <span className="mt-1.5 flex items-center gap-2 text-[11px] text-[var(--color-muted)]">
                          <time dateTime={session.updated_at}>{formatSessionDate(session.updated_at)}</time>
                          <span aria-hidden className="opacity-50">·</span>
                          <span>{session.message_count} msgs</span>
                        </span>
                      </button>
                    </li>
                  )
                })}
              </ul>
            )}
          </div>
        </div>

        {!open ? (
          <div className="hidden lg:flex flex-col items-center gap-2 py-4 px-1 border-r-0">
            <button
              type="button"
              onClick={onToggle}
              className="rounded-xl p-2.5 text-[var(--color-muted)] hover:text-amber-600 sidebar-session-item border border-[var(--color-border-subtle)] transition-all duration-200"
              aria-label="Open chat history"
              title="Chat history"
            >
              <PanelLeftOpen size={18} />
            </button>
          </div>
        ) : null}
      </aside>

      {!open ? (
        <button
          type="button"
          onClick={onToggle}
          className="fixed left-3 top-[4.25rem] z-20 lg:hidden rounded-2xl border border-[var(--color-border-subtle)] bg-[var(--color-sidebar-bg)] p-2.5 text-[var(--color-muted)] shadow-md hover:text-amber-600 hover:border-amber-600/35 transition-all duration-200"
          aria-label="Open chat history"
        >
          <PanelLeftOpen size={18} />
        </button>
      ) : null}
    </>
  )
}
