import { useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import * as api from '../api/client.js'
import { useAuth } from '../context/AuthContext.jsx'
import { getApiErrorMessage, isNetworkError } from '../utils/apiError.js'
import { ThemeToggle } from '../components/ThemeToggle.jsx'

export function SignupPage() {
  const { user, loading, loginWithToken } = useAuth()
  const navigate = useNavigate()
  const [displayName, setDisplayName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
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
    setBusy(true)
    try {
      const data = await api.signup(email.trim(), password, displayName.trim() || '')
      await loginWithToken(data.token)
      navigate('/', { replace: true })
      toast.success('Account created.')
    } catch (err) {
      const msg = isNetworkError(err)
        ? 'Cannot reach the API. Start the backend on port 8000.'
        : getApiErrorMessage(err, 'Unable to register.')
      toast.error(msg)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="min-h-screen relative flex items-center justify-center px-4 py-12 bg-[var(--color-bg)]">
      <div className="absolute top-4 right-4 z-10">
        <ThemeToggle />
      </div>
      <div
        className="w-full max-w-md rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-surface)] p-8"
        style={{ boxShadow: 'var(--shadow-card)' }}
      >
        <h1 className="text-xl font-bold tracking-[0.2em] text-[var(--color-fg)] text-center mb-1">CINERAG</h1>
        <p className="text-sm text-[var(--color-muted)] text-center mb-8">Create your account</p>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <label className="flex flex-col gap-1.5 text-sm">
            <span className="text-[var(--color-muted)]">Display name</span>
            <input
              type="text"
              autoComplete="name"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              className="rounded-xl bg-[var(--color-input-bg)] border border-[var(--color-border)] px-4 py-2.5 text-[var(--color-fg)] outline-none focus:ring-2 focus:ring-amber-500/35"
            />
          </label>
          <label className="flex flex-col gap-1.5 text-sm">
            <span className="text-[var(--color-muted)]">Email</span>
            <input
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="rounded-xl bg-[var(--color-input-bg)] border border-[var(--color-border)] px-4 py-2.5 text-[var(--color-fg)] outline-none focus:ring-2 focus:ring-amber-500/35"
            />
          </label>
          <label className="flex flex-col gap-1.5 text-sm">
            <span className="text-[var(--color-muted)]">Password</span>
            <input
              type="password"
              autoComplete="new-password"
              required
              minLength={6}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="rounded-xl bg-[var(--color-input-bg)] border border-[var(--color-border)] px-4 py-2.5 text-[var(--color-fg)] outline-none focus:ring-2 focus:ring-amber-500/35"
            />
          </label>
          <button
            type="submit"
            disabled={busy}
            className="mt-2 rounded-xl btn-neon-accent font-semibold py-3 w-full disabled:opacity-40 disabled:shadow-none disabled:filter-none"
          >
            {busy ? 'Creating…' : 'Sign up'}
          </button>
        </form>
        <p className="mt-6 text-center text-sm text-[var(--color-muted)]">
          Already have an account?{' '}
          <Link className="text-[var(--color-accent)] hover:text-[var(--color-accent-mid)] hover:underline transition-colors duration-200 font-medium" to="/login">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  )
}
