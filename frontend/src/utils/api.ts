import { API_URL } from '../config'

interface FetchOptions extends RequestInit {
  skipAuth?: boolean
}

function getTokens() {
  const raw = localStorage.getItem('auth-storage')
  if (!raw) return null
  try {
    const parsed = JSON.parse(raw)
    return parsed?.state ?? null
  } catch {
    return null
  }
}

async function refreshAccessToken(): Promise<string | null> {
  const tokens = getTokens()
  if (!tokens?.refreshToken) return null

  const res = await fetch(`${API_URL}/api/v1/auth/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: tokens.refreshToken }),
  })

  if (!res.ok) return null

  const data = await res.json()
  // Update stored tokens
  const raw = localStorage.getItem('auth-storage')
  if (raw) {
    const parsed = JSON.parse(raw)
    parsed.state.accessToken = data.access_token
    parsed.state.refreshToken = data.refresh_token
    localStorage.setItem('auth-storage', JSON.stringify(parsed))
  }
  return data.access_token
}

export function authHeaders(): HeadersInit {
  const raw = localStorage.getItem('auth-storage')
  if (!raw) return {}
  try {
    const token = JSON.parse(raw)?.state?.accessToken
    return token ? { Authorization: `Bearer ${token}` } : {}
  } catch {
    return {}
  }
}

export async function apiFetch<T = unknown>(
  path: string,
  options: FetchOptions = {}
): Promise<T> {
  const { skipAuth, ...fetchOptions } = options
  const headers = new Headers(fetchOptions.headers)

  if (!skipAuth) {
    const tokens = getTokens()
    if (tokens?.accessToken) {
      headers.set('Authorization', `Bearer ${tokens.accessToken}`)
    }
  }

  if (!headers.has('Content-Type') && fetchOptions.body && typeof fetchOptions.body === 'string') {
    headers.set('Content-Type', 'application/json')
  }

  let res = await fetch(`${API_URL}${path}`, { ...fetchOptions, headers })

  // If 401, try refreshing the token once
  if (res.status === 401 && !skipAuth) {
    const newToken = await refreshAccessToken()
    if (newToken) {
      headers.set('Authorization', `Bearer ${newToken}`)
      res = await fetch(`${API_URL}${path}`, { ...fetchOptions, headers })
    }
  }

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(error.detail || `API error: ${res.status}`)
  }

  return res.json()
}
