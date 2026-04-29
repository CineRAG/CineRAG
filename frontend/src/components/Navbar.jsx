import { Link, NavLink, useNavigate } from 'react-router-dom'
import { Flame, Bell, MessageCircle } from 'lucide-react'
import { useAuth } from '../context/AuthContext.jsx'
import { USE_MOCK } from '../api/client.js'

export function Navbar({ onNavigateAddMovie }) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const display = user?.display_name || user?.email || 'Guest'

  return (
    <header className="sticky top-0 z-50 border-b border-white/[0.07] bg-[var(--color-bg)]/95 backdrop-blur-md shadow-sm shadow-black/20">
      <div className="mx-auto flex max-w-[1400px] items-center gap-4 px-4 py-3">
        <Link
          to="/"
          className="font-bold tracking-[0.2em] text-sm sm:text-[15px] text-white whitespace-nowrap hover:text-amber-200/90 transition-colors duration-200"
        >
          CINERAG
        </Link>

        <nav className="hidden sm:flex items-center gap-6 text-xs font-semibold uppercase tracking-wider ml-6">
          <NavLink to="/" end>
            {({ isActive }) => (
              <span
                className={`relative inline-flex items-center gap-1 pb-1 ${
                  isActive ? 'text-white' : 'text-[var(--color-muted)] hover:text-zinc-100'
                }`}
              >
                {isActive ? (
                  <Flame size={14} className="text-amber-400 shrink-0" aria-hidden />
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
                  ? 'text-white border-b-2 border-amber-500'
                  : 'text-[var(--color-muted)] hover:text-zinc-100 border-b-2 border-transparent'
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
            className="flex w-full items-center gap-2 rounded-full bg-zinc-900/60 border border-white/[0.07] px-4 py-2 text-sm text-zinc-500 hover:border-amber-900/40 hover:text-zinc-400 transition-all duration-200"
          >
            <span aria-hidden className="text-zinc-600">⌕</span>
            Search movies for your list…
          </button>
        </div>

        <nav className="flex sm:hidden items-center gap-4 text-[11px] font-semibold uppercase tracking-wider mr-2">
          <NavLink
            to="/"
            end
            className={({ isActive }) => (isActive ? 'text-white' : 'text-[var(--color-muted)]')}
          >
            Board
          </NavLink>
          <NavLink
            to="/profile"
            className={({ isActive }) => (isActive ? 'text-white' : 'text-[var(--color-muted)]')}
          >
            Profile
          </NavLink>
        </nav>

        <div className="flex items-center gap-2 sm:gap-4 ml-auto">
          {USE_MOCK ? (
            <span className="hidden lg:inline rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide bg-amber-950/50 text-amber-200/95 border border-amber-700/40 animate-glow-soft">
              Mock API
            </span>
          ) : null}
          <button
            type="button"
            className="rounded-full p-2 text-[var(--color-muted)] hover:bg-white/[0.06] hover:text-zinc-200 transition-colors duration-200 hidden sm:inline-flex"
            aria-label="Messages"
          >
            <MessageCircle size={20} />
          </button>
          <button
            type="button"
            className="rounded-full p-2 text-[var(--color-muted)] hover:bg-white/[0.06] hover:text-zinc-200 transition-colors duration-200 hidden sm:inline-flex"
            aria-label="Notifications"
          >
            <Bell size={20} />
          </button>
          <div className="flex items-center gap-2 pl-1">
            <div
              className="h-9 w-9 rounded-full bg-gradient-to-br from-zinc-600 to-zinc-800 flex items-center justify-center text-[11px] font-bold ring-1 ring-white/10"
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
              <span className="text-sm font-medium truncate max-w-[8rem] text-zinc-100" title={display}>
                {display}
              </span>
              <span className="text-[11px] text-[var(--color-muted)]">Premium</span>
            </div>
          </div>
          <button
            type="button"
            className="text-xs text-[var(--color-muted)] hover:text-amber-100/90 ml-2 transition-colors duration-200"
            onClick={() => logout()}
          >
            Log out
          </button>
        </div>
      </div>
    </header>
  )
}
