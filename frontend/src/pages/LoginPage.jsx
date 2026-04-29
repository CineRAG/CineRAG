import { useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import * as api from '../api/client.js'
import { useAuth } from '../context/AuthContext.jsx'

export function LoginPage() {
  const { user, loading, loginWithToken } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[var(--color-bg)] text-[var(--color-muted)]">
        Loading…
      </div>
    )
  }
  if (user) {
    return <Navigate to="/" replace />
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      const data = await api.login(email.trim(), password)
      await loginWithToken(data.token)
      navigate('/', { replace: true })
    } catch (err) {
      const raw = typeof err.message === 'string' ? err.message : ''
      const unreachable =
        raw === 'Failed to fetch' ||
        /network|load failed|fetch/i.test(raw)
      setError(
        unreachable
          ? 'Cannot reach the API. Start the backend on port 8000, or remove VITE_USE_MOCK=false to use the built-in mock.'
          : err.body?.detail || raw || 'Login failed.'
      )
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-12 bg-[var(--color-bg)]">
      <div className="w-full max-w-md rounded-[var(--radius-card)] border border-white/10 bg-[var(--color-surface)] p-8 shadow-xl">
        <h1 className="text-xl font-bold tracking-[0.2em] text-center mb-1">CINERAG</h1>
        <p className="text-sm text-[var(--color-muted)] text-center mb-8">Sign in to continue</p>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          {error ? (
            <div className="rounded-xl bg-red-500/15 border border-red-500/30 px-3 py-2 text-sm text-red-200">
              {error}
            </div>
          ) : null}
          <label className="flex flex-col gap-1.5 text-sm">
            <span className="text-[var(--color-muted)]">Email</span>
            <input
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="rounded-xl bg-black/35 border border-white/10 px-4 py-2.5 outline-none focus:ring-2 focus:ring-amber-500/35"
            />
          </label>
          <label className="flex flex-col gap-1.5 text-sm">
            <span className="text-[var(--color-muted)]">Password</span>
            <input
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="rounded-xl bg-black/35 border border-white/10 px-4 py-2.5 outline-none focus:ring-2 focus:ring-amber-500/35"
            />
          </label>
          <button
            type="submit"
            disabled={busy}
            className="mt-2 rounded-xl btn-neon-accent font-semibold py-3 w-full disabled:opacity-40 disabled:shadow-none disabled:filter-none"
          >
            {busy ? 'Signing in…' : 'Sign in'}
          </button>
        </form>
        <p className="mt-6 text-center text-sm text-[var(--color-muted)]">
          No account?{' '}
          <Link className="text-amber-400/95 hover:text-amber-300 hover:underline transition-colors duration-200" to="/signup">
            Create one
          </Link>
        </p>
      </div>
    </div>
  )
}
