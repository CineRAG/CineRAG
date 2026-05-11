import { useEffect, useMemo, useState } from 'react'
import { Loader2, Search, X } from 'lucide-react'
import { toast } from 'sonner'
import * as api from '../api/client.js'
import { getApiErrorMessage } from '../utils/apiError.js'
import { RatingStars } from './RatingStars.jsx'

/**
 * Modal: title search via GET /api/movies/search
 */
export function MovieSearchModal({ isOpen, onClose, onAddMovie }) {
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [remoteResults, setRemoteResults] = useState([])
  const [pendingRating, setPendingRating] = useState({})

  const trimmed = query.trim()
  const rows = useMemo(() => remoteResults, [remoteResults])

  useEffect(() => {
    if (!isOpen) return
    let cancelled = false

    async function run() {
      const q = query.trim()
      if (q.length < 2) {
        setRemoteResults([])
        return
      }
      setLoading(true)
      try {
        const data = await api.searchMovies(q)
        if (!cancelled) setRemoteResults(data.results || [])
      } catch (e) {
        if (!cancelled) {
          setRemoteResults([])
          toast.error(getApiErrorMessage(e, 'Search failed.'))
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    const t = setTimeout(run, 280)
    return () => {
      cancelled = true
      clearTimeout(t)
    }
  }, [query, isOpen])

  if (!isOpen) return null

  function handleAdd(movie) {
    const rating = pendingRating[movie.movie_id]
    const r = rating && rating > 0 ? rating : null
    onAddMovie?.({
      movie_id: movie.movie_id,
      title: movie.title,
      year: movie.year,
      genres: movie.genres || [],
      rating: r,
    })
  }

  const empty = rows.length === 0 && !loading && trimmed.length >= 2
  const idleHint = trimmed.length < 2

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center p-4 backdrop-blur-sm bg-[var(--color-overlay)]"
      role="dialog"
      aria-modal="true"
      aria-labelledby="movie-search-title"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose?.()
      }}
    >
      <div
        className="w-full max-w-2xl max-h-[85vh] flex flex-col rounded-[var(--radius-card)] bg-[var(--color-surface)] border border-[var(--color-border)] overflow-hidden"
        style={{ boxShadow: 'var(--shadow-modal)' }}
      >
        <div className="flex items-center justify-between gap-3 px-5 py-4 border-b border-[var(--color-border-subtle)] shrink-0">
          <h2 id="movie-search-title" className="text-lg font-semibold text-[var(--color-fg)]">
            Search movies
          </h2>
          <button
            type="button"
            className="p-2 rounded-xl hover:bg-[var(--color-border-subtle)] text-[var(--color-muted)]"
            onClick={() => onClose?.()}
            aria-label="Close"
          >
            <X size={20} />
          </button>
        </div>

        <div className="p-5 border-b border-[var(--color-border-subtle)] shrink-0">
          <label className="flex items-center gap-3 rounded-full bg-[var(--color-input-bg)] border border-[var(--color-border)] px-4 py-2.5 focus-within:ring-2 focus-within:ring-amber-500/35 transition-shadow duration-200">
            <Search size={18} className="text-[var(--color-muted)] shrink-0" />
            <input
              autoFocus
              placeholder="Search by title (min. 2 characters)…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="flex-1 min-w-0 bg-transparent outline-none text-[var(--color-fg)] placeholder:text-[var(--color-muted)]"
            />
          </label>
          <p className="mt-2 text-xs text-[var(--color-muted)]">
            Results come from the backend corpus index. Optionally set 1–5 stars, then add to your watched
            list.
          </p>
        </div>

        <div className="flex-1 min-h-[12rem] overflow-y-auto px-5 py-3">
          {loading && trimmed.length >= 2 ? (
            <div className="flex items-center gap-2 text-[var(--color-muted)] py-3 justify-center text-sm mb-3">
              <Loader2 className="animate-spin shrink-0" size={18} aria-hidden /> Searching…
            </div>
          ) : null}
          {idleHint ? (
            <p className="text-center text-[var(--color-muted)] py-8 text-sm">
              Type at least 2 characters to search the movie catalog.
            </p>
          ) : null}
          {!loading && empty ? (
            <p className="text-center text-[var(--color-muted)] py-8">No matching titles.</p>
          ) : null}
          <ul className="space-y-4">
            {rows.map((m) => (
              <li
                key={m.movie_id}
                className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-card-row-bg)] p-4 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between gap-y-3"
              >
                <div className="min-w-0 flex-1">
                  <div className="font-medium text-[var(--color-fg)]">{m.title}</div>
                  <div className="text-sm text-[var(--color-muted)]">
                    {m.year ?? '—'}
                    {m.genres?.length ? (
                      <>
                        {' '}
                        · {m.genres.slice(0, 4).join(', ')}
                      </>
                    ) : null}
                  </div>
                  {m.plot_preview ? (
                    <p className="mt-2 text-xs text-[var(--color-muted)] leading-relaxed line-clamp-3">
                      {m.plot_preview}
                    </p>
                  ) : null}
                </div>
                <div className="flex flex-col gap-3 sm:items-end shrink-0">
                  <RatingStars
                    value={pendingRating[m.movie_id] ?? 0}
                    onChange={(rating) =>
                      setPendingRating((prev) => ({ ...prev, [m.movie_id]: rating }))
                    }
                  />
                  <button
                    type="button"
                    onClick={() => handleAdd(m)}
                    className="rounded-xl px-4 py-2 text-sm font-medium btn-neon-accent"
                  >
                    Add to watched
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  )
}
