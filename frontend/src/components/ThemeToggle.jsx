import { Moon, Sparkles, Sun } from 'lucide-react'
import { useTheme } from '../context/ThemeContext.jsx'

const LABELS = {
  dark: 'Switch to light theme',
  light: 'Switch to neon theme',
  neon: 'Switch to dark theme',
}

export function ThemeToggle({ className = '' }) {
  const { theme, cycleTheme } = useTheme()

  const Icon = theme === 'dark' ? Sun : theme === 'light' ? Sparkles : Moon

  return (
    <button
      type="button"
      onClick={cycleTheme}
      className={`theme-toggle rounded-full p-2 text-[var(--color-muted)] border border-[var(--color-border-subtle)] bg-[var(--color-surface)] hover:bg-[var(--color-surface-elevated)] hover:text-[var(--color-fg)] transition-all duration-200 shadow-sm ${className}`}
      aria-label={LABELS[theme] ?? 'Switch theme'}
      title={LABELS[theme] ?? 'Switch theme'}
    >
      <Icon size={18} strokeWidth={1.75} />
    </button>
  )
}
