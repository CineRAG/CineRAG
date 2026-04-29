import { useCallback, useEffect, useMemo, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import * as api from '../api/client.js'
import { Navbar } from '../components/Navbar.jsx'
import { MovieCard } from '../components/MovieCard.jsx'
import { MovieSearchModal } from '../components/MovieSearchModal.jsx'

export function ProfilePage() {
  const location = useLocation()
  const navigate = useNavigate()
  const [user, setUser] = useState(null)
  const [watched, setWatched] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [modalOpen, setModalOpen] = useState(false)
  const [sortBy, setSortBy] = useState('date_desc')

  const load = useCallback(async () => {
    setError('')
    try {
      const [me, watchedRes] = await Promise.all([api.getMe(), api.getWatched()])
      setUser(me)
      setWatched(watchedRes.watched || [])
    } catch (e) {
      setError(e.body?.detail || e.message || 'Failed to load profile.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  useEffect(() => {
    if (location.state?.openSearch) {
      setModalOpen(true)
      navigate(location.pathname, { replace: true, state: {} })
    }
  }, [location.state, location.pathname, navigate])

  const handleRemove = async (movieId) => {
    try {
      await api.removeWatched(movieId)
      setWatched((w) => w.filter((x) => x.movie_id !== movieId))
    } catch (e) {
      setError(e.body?.detail || e.message || 'Remove failed.')
    }
  }

  const handleRatingChange = async (movieId, rating) => {
    try {
      const updated = await api.updateRating(movieId, rating)
      setWatched((w) =>
        w.map((row) => (row.movie_id === movieId ? { ...row, rating: updated.rating } : row))
      )
    } catch (e) {
      setError(e.body?.detail || e.message || 'Update failed.')
    }
  }

  const sortedWatched = useMemo(() => {
    const copy = [...(watched || [])]
    const t = (s) => {
      const n = new Date(s).getTime()
      return Number.isFinite(n) ? n : 0
    }
    switch (sortBy) {
      case 'date_desc':
        return copy.sort((a, b) => t(b.created_at) - t(a.created_at))
      case 'date_asc':
        return copy.sort((a, b) => t(a.created_at) - t(b.created_at))
      case 'rating_desc':
        return copy.sort((a, b) => {
          const ra = a.rating
          const rb = b.rating
          if (ra == null && rb == null) return t(b.created_at) - t(a.created_at)
          if (ra == null) return 1
          if (rb == null) return -1
          return rb - ra
        })
      case 'rating_asc':
        return copy.sort((a, b) => {
          const ra = a.rating
          const rb = b.rating
          if (ra == null && rb == null) return t(b.created_at) - t(a.created_at)
          if (ra == null) return 1
          if (rb == null) return -1
          return ra - rb
        })
      default:
        return copy
    }
  }, [watched, sortBy])

  const handleAddFromModal = async (movie) => {
    try {
      await api.addWatched(
        movie.movie_id,
        movie.title,
        movie.year,
        movie.genres,
        movie.rating
      )
      await load()
      setModalOpen(false)
    } catch (e) {
      const msg = e.body?.detail || e.message || 'Could not add.'
      setError(msg)
    }
  }

  return (
    <div className="min-h-screen flex flex-col bg-[var(--color-bg)]">
      <Navbar />
      <main className="flex-1 max-w-[1200px] w-full mx-auto px-4 py-10">
        <div className="flex flex-wrap items-end justify-between gap-4 mb-10">
          <div>
            <h1 className="text-2xl font-bold text-white tracking-tight">Your profile</h1>
            <p className="text-[var(--color-muted)] mt-1">
              {loading
                ? 'Loading…'
                : user
                  ? `${user.display_name || 'Member'} · ${user.email}`
                  : ''}
            </p>
          </div>
          <button
            type="button"
            onClick={() => setModalOpen(true)}
            className="rounded-full btn-neon-accent font-semibold px-5 py-2.5"
          >
            Add movie
          </button>
        </div>

        {error ? (
          <div className="mb-6 rounded-xl bg-red-500/15 border border-red-500/30 px-4 py-3 text-sm text-red-200">
            {error}
          </div>
        ) : null}

        <section>
          <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-[var(--color-muted)]">
              Watched movies ({watched.length})
            </h2>
            {watched.length > 0 ? (
              <label className="flex items-center gap-2 text-xs text-[var(--color-muted)]">
                <span className="shrink-0">Sort</span>
                <select
                  value={sortBy}
                  onChange={(e) => setSortBy(e.target.value)}
                  className="rounded-lg bg-black/45 border border-white/15 px-2.5 py-1.5 text-sm text-white outline-none focus:ring-2 focus:ring-amber-500/35 transition-all duration-200"
                >
                  <option value="date_desc">Date added · newest first</option>
                  <option value="date_asc">Date added · oldest first</option>
                  <option value="rating_desc">Rating · high → low</option>
                  <option value="rating_asc">Rating · low → high</option>
                </select>
              </label>
            ) : null}
          </div>
          {loading ? (
            <p className="text-[var(--color-muted)]">Loading watched list…</p>
          ) : watched.length === 0 ? (
            <p className="text-[var(--color-muted)] rounded-[var(--radius-card)] border border-dashed border-white/15 p-10 text-center">
              Nothing here yet. Add films you have seen so retrieval can avoid already-watched picks.
            </p>
          ) : (
            <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {sortedWatched.map((row) => (
                <MovieCard
                  key={row.id}
                  movieId={row.movie_id}
                  title={row.title}
                  year={row.year}
                  genres={row.genres || []}
                  userRating={row.rating ?? 0}
                  mode="profile"
                  onRemove={handleRemove}
                  onRatingChange={handleRatingChange}
                />
              ))}
            </div>
          )}
        </section>
      </main>

      <MovieSearchModal
        key={modalOpen ? 'open' : 'closed'}
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        onAddMovie={handleAddFromModal}
      />
    </div>
  )
}
