import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { User } from '../types'
import { API_URL } from '../config'
import { supabase } from '../lib/supabase'

interface AuthState {
  user: User | null
  accessToken: string | null
  isAuthenticated: boolean
  isLoading: boolean
  sessionChecked: boolean

  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string, fullName: string) => Promise<void>
  loginWithGoogle: () => Promise<void>
  logout: () => void
  fetchUser: () => Promise<void>
  initSession: () => Promise<void>
}

async function syncUserToBackend(accessToken: string): Promise<User> {
  const headers = { Authorization: `Bearer ${accessToken}` }

  // Try /auth/me first (works for both Supabase and legacy JWT)
  const res = await fetch(`${API_URL}/api/v1/auth/me`, { headers })
  if (res.ok) {
    return res.json()
  }

  // First-time Supabase user: provision via /auth/supabase-sync
  const provision = await fetch(`${API_URL}/api/v1/auth/supabase-sync`, {
    method: 'POST',
    headers: { ...headers, 'Content-Type': 'application/json' },
  })
  if (provision.ok) {
    return provision.json()
  }

  // Both failed — log details for debugging
  const detail = await provision.text().catch(() => 'unknown error')
  console.error(`[auth] sync failed: /me=${res.status}, /supabase-sync=${provision.status}: ${detail}`)
  throw new Error('Failed to sync user profile')
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      accessToken: null,
      isAuthenticated: false,
      isLoading: false,
      sessionChecked: false,

      initSession: async () => {
        try {
          const { data: { session } } = await supabase.auth.getSession()
          if (session) {
            set({ accessToken: session.access_token, isAuthenticated: true })
            try {
              const user = await syncUserToBackend(session.access_token)
              set({ user })
            } catch (e) {
              console.warn('[auth] Backend sync failed during init:', e)
              // Keep isAuthenticated true — user can still see pages,
              // profile just won't show until next successful sync
            }
          } else {
            // No Supabase session — check if we have a persisted token (legacy)
            const { accessToken: stored } = get()
            if (stored) {
              try {
                const user = await syncUserToBackend(stored)
                set({ user, isAuthenticated: true })
              } catch {
                // Stale token — clear auth state
                set({ user: null, accessToken: null, isAuthenticated: false })
              }
            }
          }
        } finally {
          set({ sessionChecked: true })
        }

        // Listen for auth state changes (token refresh, sign out, OAuth redirect)
        supabase.auth.onAuthStateChange(async (event, session) => {
          if (session) {
            set({ accessToken: session.access_token, isAuthenticated: true, sessionChecked: true })
            // Sync user to backend on sign-in or token refresh
            if (event === 'SIGNED_IN' || event === 'TOKEN_REFRESHED') {
              try {
                const user = await syncUserToBackend(session.access_token)
                set({ user })
              } catch {
                // backend may be down
              }
            }
          } else {
            set({ user: null, accessToken: null, isAuthenticated: false, sessionChecked: true })
          }
        })
      },

      login: async (email, password) => {
        set({ isLoading: true })
        try {
          const { data, error } = await supabase.auth.signInWithPassword({ email, password })
          if (error) throw new Error(error.message)
          const token = data.session.access_token
          const user = await syncUserToBackend(token)
          set({ user, accessToken: token, isAuthenticated: true })
        } finally {
          set({ isLoading: false })
        }
      },

      register: async (email, password, fullName) => {
        set({ isLoading: true })
        try {
          const { data, error } = await supabase.auth.signUp({
            email,
            password,
            options: { data: { full_name: fullName } },
          })
          if (error) throw new Error(error.message)
          if (!data.session) {
            throw new Error('Check your email for a confirmation link, then sign in.')
          }
          const token = data.session.access_token
          const user = await syncUserToBackend(token)
          set({ user, accessToken: token, isAuthenticated: true })
        } finally {
          set({ isLoading: false })
        }
      },

      loginWithGoogle: async () => {
        set({ isLoading: true })
        try {
          const { error } = await supabase.auth.signInWithOAuth({
            provider: 'google',
            options: { redirectTo: window.location.origin },
          })
          if (error) throw new Error(error.message)
          // Redirect happens — state will be picked up by initSession on return
        } finally {
          set({ isLoading: false })
        }
      },

      logout: () => {
        supabase.auth.signOut()
        set({ user: null, accessToken: null, isAuthenticated: false })
      },

      fetchUser: async () => {
        const { accessToken } = get()
        if (!accessToken) return
        try {
          const user = await syncUserToBackend(accessToken)
          set({ user })
        } catch {
          // silently fail
        }
      },
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({
        accessToken: state.accessToken,
        user: state.user,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
)
