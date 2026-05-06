import { Link, NavLink, useNavigate } from 'react-router-dom'
import { Bell, Flame, MessageCircle } from 'lucide-react'
import { useAuth } from '../context/AuthContext.jsx'
import { ThemeToggle } from './ThemeToggle.jsx'

export function Navbar({ onNavigateAddMovie }) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const display = user?.display_name || user?.email || 'Guest'

  return (
    <header
      className="sticky top-0 z-50 border-b border-[var(--color-border-subtle)] bg-[var(--color-bg)]/95 backdrop-blur-md"
      style={{ boxShadow: 'var(--shadow-header)' }}
    >
      <div className="mx-auto flex max-w-[1400px] items-center gap-4 px-4 py-3">
        <Link
          to="/"
          className="font-bold tracking-[0.2em] text-sm sm:text-[15px] text-[var(--color-fg)] whitespace-nowrap hover:text-[var(--color-logo-hover)] transition-colors duration-200"
        >
          CINERAG
        </Link>

        <nav className="hidden sm:flex items-center gap-6 text-xs font-semibold uppercase tracking-wider ml-6">
          <NavLink to="/" end>
            {({ isActive }) => (
              <span
                className={`relative inline-flex items-center gap-1 pb-1 ${
                  isActive
                    ? 'text-[var(--color-fg)]'
                    : 'text-[var(--color-muted)] hover:text-[var(--color-fg-secondary)]'
                }`}
              >
                {isActive ? (
                  <Flame size={14} className="text-amber-500 shrink-0" aria-hidden />
                ) : null}
                Board
                {isActive ? (
                  <span className="absolute bottom-0 left-0 right-0 h-[2px] rounded-full bg-gradient-to-r from-transparent via-amber-600 to-amber-400 opacity-90" />
                ) : null}
              </span>
            )}
          </NavLink>
          <NavLink
            to="/profile"
            className={({ isActive }) =>
              `pb-1 transition-colors duration-200 ${
                isActive
                  ? 'text-[var(--color-fg)] border-b-2 border-amber-500'
                  : 'text-[var(--color-muted)] hover:text-[var(--color-fg-secondary)] border-b-2 border-transparent'
              }`
            }
          >
            Profile
          </NavLink>
        </nav>

        <div className="flex-1 max-w-xl mx-4 hidden md:block">
          <button
            type="button"
            onClick={() => {
              navigate('/profile', { state: { openSearch: true } })
              onNavigateAddMovie?.()
            }}
            className="flex w-full items-center gap-2 rounded-full border border-[var(--color-border-subtle)] px-4 py-2 text-sm transition-all duration-200 bg-[var(--color-nav-search-bg)] text-[var(--color-nav-search-fg)] hover:border-amber-600/35 hover:text-[var(--color-muted)]"
          >
            <span aria-hidden className="opacity-70">⌕</span>
            Search movies for your list…
          </button>
        </div>

        <nav className="flex sm:hidden items-center gap-4 text-[11px] font-semibold uppercase tracking-wider mr-2">
          <NavLink
            to="/"
            end
            className={({ isActive }) =>
              isActive ? 'text-[var(--color-fg)]' : 'text-[var(--color-muted)]'
            }
          >
            Board
          </NavLink>
          <NavLink
            to="/profile"
            className={({ isActive }) =>
              isActive ? 'text-[var(--color-fg)]' : 'text-[var(--color-muted)]'
            }
          >
            Profile
          </NavLink>
        </nav>

        <div className="flex items-center gap-1 sm:gap-2 ml-auto">
          <ThemeToggle />
          <button
            type="button"
            className="rounded-full p-2 text-[var(--color-muted)] hover:bg-[var(--color-border-subtle)] hover:text-[var(--color-fg)] transition-colors duration-200 hidden sm:inline-flex"
            aria-label="Messages"
          >
            <MessageCircle size={20} />
          </button>
          <button
            type="button"
            className="rounded-full p-2 text-[var(--color-muted)] hover:bg-[var(--color-border-subtle)] hover:text-[var(--color-fg)] transition-colors duration-200 hidden sm:inline-flex"
            aria-label="Notifications"
          >
            <Bell size={20} />
          </button>
          <div className="flex items-center gap-2 pl-1">
            <div
              className="h-9 w-9 rounded-full bg-gradient-to-br from-amber-700/80 to-stone-800 flex items-center justify-center text-[11px] font-bold text-white ring-1 ring-[var(--color-border)]"
              aria-hidden
            >
              {display
                .split(/\s+/)
                .slice(0, 2)
                .map((s) => s[0])
                .join('')
                .slice(0, 2)}
            </div>
            <div className="hidden sm:flex flex-col min-w-0">
              <span className="text-sm font-medium truncate max-w-[8rem] text-[var(--color-fg)]" title={display}>
                {display}
              </span>
              <span className="text-[11px] text-[var(--color-muted)]">Premium</span>
            </div>
          </div>
          <button
            type="button"
            className="text-xs text-[var(--color-muted)] hover:text-[var(--color-accent)] ml-1 sm:ml-2 transition-colors duration-200"
            onClick={() => logout()}
          >
            Log out
          </button>
        </div>
      </div>
    </header>
  )
}
