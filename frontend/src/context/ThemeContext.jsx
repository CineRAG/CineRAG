import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react'
import { applyTheme, getStoredTheme, nextTheme } from '../theme/storage.js'

const ThemeContext = createContext(null)

export function ThemeProvider({ children }) {
  const [theme, setThemeState] = useState(getStoredTheme)

  useEffect(() => {
    applyTheme(theme)
  }, [theme])

  const setTheme = useCallback((value) => setThemeState(value), [])
  const setLight = useCallback(() => setThemeState('light'), [])
  const setDark = useCallback(() => setThemeState('dark'), [])
  const setNeon = useCallback(() => setThemeState('neon'), [])
  const cycleTheme = useCallback(() => {
    setThemeState((t) => nextTheme(t))
  }, [])

  const value = useMemo(
    () => ({
      theme,
      setTheme,
      setLight,
      setDark,
      setNeon,
      cycleTheme,
      isLight: theme === 'light',
      isDark: theme === 'dark',
      isNeon: theme === 'neon',
    }),
    [theme, setTheme, setLight, setDark, setNeon, cycleTheme]
  )

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components -- hook paired with Provider
export function useTheme() {
  const ctx = useContext(ThemeContext)
  if (!ctx) throw new Error('useTheme must be used within ThemeProvider')
  return ctx
}
