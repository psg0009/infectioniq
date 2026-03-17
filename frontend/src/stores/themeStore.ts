import { create } from 'zustand'

type Theme = 'light' | 'dark'

interface ThemeState {
  theme: Theme
  setTheme: (theme: Theme) => void
  toggleTheme: () => void
}

function getInitialTheme(): Theme {
  if (typeof window === 'undefined') return 'light'
  // One-time migration: reset to light if old version
  const version = localStorage.getItem('iq-theme-v')
  if (version !== '2') {
    localStorage.setItem('iq-theme', 'light')
    localStorage.setItem('iq-theme-v', '2')
    return 'light'
  }
  const stored = localStorage.getItem('iq-theme')
  if (stored === 'dark' || stored === 'light') return stored
  return 'light'
}

function applyTheme(theme: Theme) {
  const root = document.documentElement
  root.classList.add('theme-transitioning')
  // Force clean state
  root.classList.remove('dark')
  if (theme === 'dark') {
    root.classList.add('dark')
  }
  localStorage.setItem('iq-theme', theme)
  setTimeout(() => root.classList.remove('theme-transitioning'), 350)
}

// Apply on load immediately
const initial = getInitialTheme()
applyTheme(initial)

export const useThemeStore = create<ThemeState>((set, get) => ({
  theme: initial,
  setTheme: (theme) => {
    applyTheme(theme)
    set({ theme })
  },
  toggleTheme: () => {
    const current = get().theme
    const next: Theme = current === 'dark' ? 'light' : 'dark'
    applyTheme(next)
    set({ theme: next })
  },
}))
