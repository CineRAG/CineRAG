import { Moon, Sun } from 'lucide-react'
import { useTheme } from '../context/ThemeContext.jsx'

export function ThemeToggle({ className = '' }) {
  const { theme, toggleTheme } = useTheme()
  return (
    <button
      type="button"
      onClick={toggleTheme}
      className={`rounded-full p-2 text-[var(--color-muted)] border border-[var(--color-border-subtle)] bg-[var(--color-surface)] hover:bg-[var(--color-surface-elevated)] hover:text-[var(--color-fg)] transition-colors duration-200 shadow-sm ${className}`}
      aria-label={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
    >
      {theme === 'dark' ? <Sun size={18} strokeWidth={1.75} /> : <Moon size={18} strokeWidth={1.75} />}
    </button>
  )
}
