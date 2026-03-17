import { useEffect, useRef, useCallback } from 'react'
import { useAuthStore } from '../stores/authStore'

const WS_BASE = import.meta.env.VITE_WS_URL || `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}`

interface UseWebSocketOptions {
  onMessage?: (data: unknown) => void
  onOpen?: () => void
  onClose?: () => void
  autoReconnect?: boolean
  reconnectInterval?: number
}

export function useWebSocket(path: string, options: UseWebSocketOptions = {}) {
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>()
  const { onMessage, onOpen, onClose, autoReconnect = true, reconnectInterval = 3000 } = options
  const accessToken = useAuthStore((s) => s.accessToken)

  const connect = useCallback(() => {
    if (!accessToken) return // Don't connect without auth
    const url = `${WS_BASE}/ws${path}?token=${accessToken}`
    const ws = new WebSocket(url)

    ws.onopen = () => {
      onOpen?.()
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        onMessage?.(data)
      } catch {
        // non-JSON message (e.g., pong)
      }
    }

    ws.onclose = () => {
      onClose?.()
      if (autoReconnect) {
        reconnectTimer.current = setTimeout(connect, reconnectInterval)
      }
    }

    ws.onerror = () => {
      ws.close()
    }

    wsRef.current = ws
  }, [path, accessToken, onMessage, onOpen, onClose, autoReconnect, reconnectInterval])

  useEffect(() => {
    connect()
    return () => {
      clearTimeout(reconnectTimer.current)
      wsRef.current?.close()
    }
  }, [connect])

  const send = useCallback((data: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(data)
    }
  }, [])

  return { send }
}
