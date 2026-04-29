import { useEffect, useMemo, useState } from 'react'
import { Loader2, Search, X } from 'lucide-react'
import * as api from '../api/client.js'
import { DEMO_SEARCH_CATALOG } from '../data/demoMovies.js'
import { moviePosterSrc } from '../utils/moviePoster.js'
import { RatingStars } from './RatingStars.jsx'

function PosterThumb({ movie }) {
  const [failed, setFailed] = useState(false)
  const src = moviePosterSrc(movie)
  if (failed) {
    const initials = (movie.title || '?')
      .replace(/^(?:A |An |The )/i, '')
      .slice(0, 2)
      .toUpperCase()
    return (
      <div
        className="w-[88px] h-[132px] rounded-xl border border-white/10 shrink-0 bg-gradient-to-br from-zinc-700 to-zinc-950 flex items-center justify-center text-sm font-semibold text-zinc-400"
        aria-hidden
      >
        {initials}
      </div>
    )
  }
  return (
    <img
      src={src}
      alt=""
      loading="lazy"
      className="w-[88px] h-[132px] rounded-xl object-cover border border-white/10 shrink-0 bg-zinc-900"
      onError={() => setFailed(true)}
    />
  )
}

function mergeByMovieId(remote, localSubset) {
  const seen = new Set((remote || []).map((r) => r.movie_id))
  const out = [...(remote || [])]
  for (const item of localSubset) {
    if (!seen.has(item.movie_id)) {
      out.push(item)
      seen.add(item.movie_id)
    }
  }
  return out
}

function filterDemoCatalog(queryTrimmed) {
  const q = queryTrimmed.toLowerCase()
  if (q.length < 2) return DEMO_SEARCH_CATALOG
  return DEMO_SEARCH_CATALOG.filter(
    (m) =>
      m.title.toLowerCase().includes(q) ||
      (m.genres || []).some((g) => g.toLowerCase().includes(q))
  )
}

/**
 * Modal: title search via GET /api/movies/search + always-available demo catalog.
 */
export function MovieSearchModal({ isOpen, onClose, onAddMovie }) {
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [remoteResults, setRemoteResults] = useState([])
  const [pendingRating, setPendingRating] = useState({})

  const trimmed = query.trim()
  const demoMatches = useMemo(() => filterDemoCatalog(trimmed), [trimmed])

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
      } catch {
        if (!cancelled) setRemoteResults([])
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

  const displayResults = useMemo(() => {
    if (trimmed.length < 2) {
      return { rows: demoMatches, mode: 'demo-browse' }
    }
    const merged = mergeByMovieId(remoteResults, demoMatches)
    return { rows: merged, mode: 'search' }
  }, [trimmed, remoteResults, demoMatches])

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

  const { rows, mode } = displayResults
  const empty = rows.length === 0 && !loading

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="movie-search-title"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose?.()
      }}
    >
      <div className="w-full max-w-2xl max-h-[85vh] flex flex-col rounded-[var(--radius-card)] bg-[var(--color-surface)] border border-white/10 shadow-2xl overflow-hidden">
        <div className="flex items-center justify-between gap-3 px-5 py-4 border-b border-white/10 shrink-0">
          <h2 id="movie-search-title" className="text-lg font-semibold">
            Search movies
          </h2>
          <button
            type="button"
            className="p-2 rounded-xl hover:bg-white/10 text-[var(--color-muted)]"
            onClick={() => onClose?.()}
            aria-label="Close"
          >
            <X size={20} />
          </button>
        </div>

        <div className="p-5 border-b border-white/10 shrink-0">
          <label className="flex items-center gap-3 rounded-full bg-black/35 border border-white/10 px-4 py-2.5 focus-within:ring-2 focus-within:ring-amber-500/35 transition-shadow duration-200">
            <Search size={18} className="text-[var(--color-muted)] shrink-0" />
            <input
              autoFocus
              placeholder="Search by title (or scroll demo list)…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="flex-1 min-w-0 bg-transparent outline-none placeholder:text-[#585858]"
            />
          </label>
          <p className="mt-2 text-xs text-[var(--color-muted)]">
            {mode === 'demo-browse' ? (
              <>
                <span className="text-amber-200/95 font-medium">Demo catalog</span> — try ratings and
                Add to watched without the corpus index. Type 2+ letters to query the API and merge demo
                matches.
              </>
            ) : (
              <>
                Corpus title search plus matching demo titles. Optionally set 1–5 stars, then add to your
                watched list.
              </>
            )}
          </p>
        </div>

        <div className="flex-1 min-h-[12rem] overflow-y-auto px-5 py-3">
          {loading && trimmed.length >= 2 ? (
            <div className="flex items-center gap-2 text-[var(--color-muted)] py-3 justify-center text-sm mb-3">
              <Loader2 className="animate-spin shrink-0" size={18} aria-hidden /> Contacting corpus
              search…
            </div>
          ) : null}
          {!loading && empty ? (
            <p className="text-center text-[var(--color-muted)] py-8">No matching titles.</p>
          ) : null}
          <ul className="space-y-4">
            {rows.map((m) => (
              <li
                key={m.movie_id}
                className="rounded-2xl border border-white/[0.06] bg-black/20 p-4 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between gap-y-3"
              >
                <PosterThumb movie={m} />
                <div className="min-w-0 flex-1">
                  {String(m.movie_id).startsWith('demo_') ? (
                    <span className="inline-block mb-1 text-[10px] font-semibold uppercase tracking-wide px-2 py-0.5 rounded-full bg-amber-950/55 text-amber-200/95 border border-amber-700/40">
                      Demo
                    </span>
                  ) : null}
                  <div className="font-medium text-white">{m.title}</div>
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
                    <p className="mt-2 text-xs text-[#8a8a8a] leading-relaxed line-clamp-3">
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
