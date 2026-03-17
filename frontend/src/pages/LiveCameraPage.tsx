import { useState, useRef, useEffect, useCallback } from 'react'
import { Camera, CameraOff, Circle, AlertCircle, Wifi, WifiOff, Users, Shield, ShieldAlert } from 'lucide-react'
import { useAuthStore } from '../stores/authStore'

const WS_BASE = import.meta.env.VITE_WS_URL
  || `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}`

const FRAME_INTERVAL_MS = 500 // 2 FPS

interface PersonDetection {
  track_id: number
  bbox: number[]
  confidence: number
  hands_detected: number
  is_sanitizing: boolean
  gesture_score: number
  zone: string | null
  state: string
  compliant: boolean
}

interface DetectionResult {
  type: string
  frame: number
  persons_detected: number
  persons: PersonDetection[]
  events: Array<{ type: string; person_track_id: number; compliant: boolean }>
  message?: string
}

export default function LiveCameraPage() {
  const videoRef = useRef<HTMLVideoElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const overlayRef = useRef<HTMLCanvasElement>(null)
  const [streaming, setStreaming] = useState(false)
  const [sending, setSending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [devices, setDevices] = useState<MediaDeviceInfo[]>([])
  const [selectedDevice, setSelectedDevice] = useState<string>('')
  const [frameCount, setFrameCount] = useState(0)
  const [wsConnected, setWsConnected] = useState(false)
  const [detection, setDetection] = useState<DetectionResult | null>(null)
  const [eventLog, setEventLog] = useState<Array<{ time: string; text: string; type: string }>>([])
  const streamRef = useRef<MediaStream | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const intervalRef = useRef<number | null>(null)
  const accessToken = useAuthStore((s) => s.accessToken)

  // List available cameras
  useEffect(() => {
    navigator.mediaDevices?.enumerateDevices().then((devs) => {
      const cameras = devs.filter((d) => d.kind === 'videoinput')
      setDevices(cameras)
      if (cameras.length > 0 && !selectedDevice) {
        setSelectedDevice(cameras[0].deviceId)
      }
    }).catch(() => {
      setError('Cannot enumerate devices. Allow camera permission first.')
    })
  }, [selectedDevice])

  // Draw detection overlays on the video
  const drawOverlay = useCallback((result: DetectionResult) => {
    const overlay = overlayRef.current
    const video = videoRef.current
    if (!overlay || !video) return

    overlay.width = video.videoWidth || 1280
    overlay.height = video.videoHeight || 720
    const ctx = overlay.getContext('2d')
    if (!ctx) return

    ctx.clearRect(0, 0, overlay.width, overlay.height)

    for (const person of result.persons) {
      const [x1, y1, x2, y2] = person.bbox

      // Color based on state
      let color = '#6b7280' // gray default
      if (person.state === 'CLEAN') color = '#22c55e'
      else if (person.state === 'POTENTIALLY_CONTAMINATED') color = '#eab308'
      else if (person.state === 'CONTAMINATED') color = '#f97316'
      else if (person.state === 'DIRTY') color = '#ef4444'

      // Bounding box
      ctx.strokeStyle = color
      ctx.lineWidth = 2
      ctx.strokeRect(x1, y1, x2 - x1, y2 - y1)

      // Label background
      const label = `ID:${person.track_id} [${person.state}]`
      ctx.font = '14px monospace'
      const metrics = ctx.measureText(label)
      ctx.fillStyle = color
      ctx.fillRect(x1, y1 - 20, metrics.width + 8, 20)

      // Label text
      ctx.fillStyle = '#fff'
      ctx.fillText(label, x1 + 4, y1 - 5)

      // Hand/gesture info
      if (person.hands_detected > 0) {
        const info = person.is_sanitizing
          ? `Sanitizing (${(person.gesture_score * 100).toFixed(0)}%)`
          : `Hands: ${person.hands_detected}`
        ctx.fillStyle = person.is_sanitizing ? '#22c55e' : '#94a3b8'
        ctx.font = '12px monospace'
        ctx.fillText(info, x1, y2 + 15)
      }

      // Zone badge
      if (person.zone) {
        ctx.fillStyle = 'rgba(0,0,0,0.6)'
        ctx.fillRect(x2 - 80, y1, 80, 18)
        ctx.fillStyle = '#fff'
        ctx.font = '11px monospace'
        ctx.fillText(person.zone, x2 - 76, y1 + 13)
      }
    }
  }, [])

  const connectWebSocket = useCallback(() => {
    if (!accessToken) return
    const ws = new WebSocket(`${WS_BASE}/ws/camera/stream?token=${accessToken}`)
    ws.onopen = () => setWsConnected(true)
    ws.onclose = () => setWsConnected(false)
    ws.onerror = () => setWsConnected(false)
    ws.onmessage = (ev) => {
      try {
        const msg: DetectionResult = JSON.parse(ev.data)
        if (msg.type === 'detection') {
          setFrameCount(msg.frame)
          setDetection(msg)
          drawOverlay(msg)
          // Log events
          if (msg.events && msg.events.length > 0) {
            const now = new Date().toLocaleTimeString()
            const newEvents = msg.events.map((e) => ({
              time: now,
              text: `Person #${e.person_track_id} ${e.type} — ${e.compliant ? 'COMPLIANT' : 'NON-COMPLIANT'}`,
              type: e.compliant ? 'compliant' : 'violation',
            }))
            setEventLog((prev) => [...newEvents, ...prev].slice(0, 50))
          }
        } else if (msg.type === 'ack') {
          setFrameCount(msg.frame)
        } else if (msg.type === 'error') {
          setError(msg.message || 'CV processing error')
        }
      } catch { /* ignore non-json */ }
    }
    wsRef.current = ws
  }, [accessToken, drawOverlay])

  const captureAndSend = useCallback(() => {
    const video = videoRef.current
    const canvas = canvasRef.current
    const ws = wsRef.current
    if (!video || !canvas || !ws || ws.readyState !== WebSocket.OPEN) return

    canvas.width = video.videoWidth
    canvas.height = video.videoHeight
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    ctx.drawImage(video, 0, 0)
    const dataUrl = canvas.toDataURL('image/jpeg', 0.7)
    const base64 = dataUrl.split(',')[1]

    ws.send(JSON.stringify({
      type: 'frame',
      data: base64,
      timestamp: new Date().toISOString(),
      width: canvas.width,
      height: canvas.height,
    }))
  }, [])

  const startCamera = useCallback(async () => {
    setError(null)
    try {
      const constraints: MediaStreamConstraints = {
        video: selectedDevice
          ? { deviceId: { exact: selectedDevice }, width: 1280, height: 720 }
          : { width: 1280, height: 720 },
        audio: false,
      }
      const stream = await navigator.mediaDevices.getUserMedia(constraints)
      streamRef.current = stream
      if (videoRef.current) {
        videoRef.current.srcObject = stream
        await videoRef.current.play()
      }
      setStreaming(true)
    } catch (err: any) {
      if (err.name === 'NotAllowedError') {
        setError('Camera permission denied. Please allow camera access in your browser.')
      } else if (err.name === 'NotFoundError') {
        setError('No camera found. Please connect a camera.')
      } else {
        setError(`Camera error: ${err.message}`)
      }
    }
  }, [selectedDevice])

  const stopCamera = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }
    setSending(false)
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop())
      streamRef.current = null
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null
    }
    setStreaming(false)
    setFrameCount(0)
    setDetection(null)
    setEventLog([])
  }, [])

  const toggleSending = useCallback(() => {
    if (sending) {
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
        intervalRef.current = null
      }
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
      setSending(false)
    } else {
      connectWebSocket()
      intervalRef.current = window.setInterval(captureAndSend, FRAME_INTERVAL_MS)
      setSending(true)
    }
  }, [sending, connectWebSocket, captureAndSend])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
      if (wsRef.current) wsRef.current.close()
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((t) => t.stop())
      }
    }
  }, [])

  const compliantCount = detection?.persons.filter((p) => p.compliant).length ?? 0
  const totalPersons = detection?.persons_detected ?? 0

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Live Camera Feed</h1>
        <p className="text-slate-500 dark:text-slate-400 mt-1">
          Real-time OR monitoring with CV-powered hand hygiene detection.
        </p>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-100 rounded-xl p-4 flex items-center gap-3">
          <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0" />
          <span className="text-red-700 text-sm">{error}</span>
        </div>
      )}

      {/* Controls */}
      <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-card dark:shadow-none border border-slate-100 dark:border-slate-700 p-4">
        <div className="flex items-center gap-4 flex-wrap">
          {devices.length > 0 && (
            <div>
              <label className="block text-xs font-medium text-slate-500 dark:text-slate-400 mb-1">Camera</label>
              <select
                value={selectedDevice}
                onChange={(e) => setSelectedDevice(e.target.value)}
                disabled={streaming}
                title="Select camera"
                className="border border-slate-300 dark:border-slate-600 dark:bg-slate-700 dark:text-white rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 disabled:opacity-50"
              >
                {devices.map((d, i) => (
                  <option key={d.deviceId} value={d.deviceId}>
                    {d.label || `Camera ${i + 1}`}
                  </option>
                ))}
              </select>
            </div>
          )}

          {!streaming ? (
            <button
              type="button"
              onClick={startCamera}
              className="inline-flex items-center gap-2 px-4 py-2 bg-green-600 text-white font-medium rounded-lg hover:bg-green-700 transition-colors"
            >
              <Camera className="w-4 h-4" /> Start Camera
            </button>
          ) : (
            <>
              <button
                type="button"
                onClick={stopCamera}
                className="inline-flex items-center gap-2 px-4 py-2 bg-red-600 text-white font-medium rounded-lg hover:bg-red-700 transition-colors"
              >
                <CameraOff className="w-4 h-4" /> Stop Camera
              </button>

              <button
                type="button"
                onClick={toggleSending}
                className={`inline-flex items-center gap-2 px-4 py-2 font-medium rounded-lg transition-colors ${
                  sending
                    ? 'bg-orange-600 text-white hover:bg-orange-700'
                    : 'bg-gradient-brand text-white hover:opacity-90 shadow-glow-brand'
                }`}
              >
                {sending ? (
                  <><WifiOff className="w-4 h-4" /> Stop Streaming</>
                ) : (
                  <><Wifi className="w-4 h-4" /> Stream to Server</>
                )}
              </button>
            </>
          )}

          {streaming && (
            <div className="flex items-center gap-4 text-sm">
              <div className="flex items-center gap-2 text-green-600">
                <Circle className="w-3 h-3 fill-current animate-pulse" />
                Live
              </div>
              {sending && (
                <>
                  <div className={`flex items-center gap-1 ${wsConnected ? 'text-brand-600' : 'text-red-500'}`}>
                    {wsConnected ? <Wifi className="w-3 h-3" /> : <WifiOff className="w-3 h-3" />}
                    {wsConnected ? 'Connected' : 'Disconnected'}
                  </div>
                  <span className="text-slate-500 dark:text-slate-400">Frames: {frameCount}</span>
                </>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Detection Stats */}
      {sending && detection && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-card dark:shadow-none border border-slate-100 dark:border-slate-700 p-4">
            <div className="flex items-center gap-2 text-slate-500 dark:text-slate-400 text-sm mb-1">
              <Users className="w-4 h-4" /> Persons Detected
            </div>
            <p className="text-2xl font-bold text-slate-900 dark:text-white">{totalPersons}</p>
          </div>
          <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-card dark:shadow-none border border-slate-100 dark:border-slate-700 p-4">
            <div className="flex items-center gap-2 text-green-600 text-sm mb-1">
              <Shield className="w-4 h-4" /> Compliant
            </div>
            <p className="text-2xl font-bold text-green-700">{compliantCount}</p>
          </div>
          <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-card dark:shadow-none border border-slate-100 dark:border-slate-700 p-4">
            <div className="flex items-center gap-2 text-red-500 text-sm mb-1">
              <ShieldAlert className="w-4 h-4" /> Non-Compliant
            </div>
            <p className="text-2xl font-bold text-red-600">{totalPersons - compliantCount}</p>
          </div>
          <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-card dark:shadow-none border border-slate-100 dark:border-slate-700 p-4">
            <div className="flex items-center gap-2 text-slate-500 dark:text-slate-400 text-sm mb-1">
              <Camera className="w-4 h-4" /> Frame Rate
            </div>
            <p className="text-2xl font-bold text-slate-900 dark:text-white">2 FPS</p>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Video Feed */}
        <div className="lg:col-span-2 bg-black rounded-2xl overflow-hidden relative" style={{ minHeight: 400 }}>
          <video
            ref={videoRef}
            className="w-full h-full object-contain"
            playsInline
            muted
          />
          {/* Detection overlay canvas */}
          <canvas
            ref={overlayRef}
            className="absolute inset-0 w-full h-full object-contain pointer-events-none"
          />
          <canvas ref={canvasRef} className="hidden" />

          {!streaming && (
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="text-center text-white/60">
                <Camera className="w-16 h-16 mx-auto mb-3" />
                <p className="text-lg font-medium">Camera not active</p>
                <p className="text-sm mt-1">Click "Start Camera" to begin monitoring</p>
              </div>
            </div>
          )}
        </div>

        {/* Event Log */}
        <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-card dark:shadow-none border border-slate-100 dark:border-slate-700 p-4">
          <h3 className="text-sm font-semibold text-slate-900 dark:text-white mb-3">Detection Events</h3>
          {eventLog.length === 0 ? (
            <p className="text-sm text-slate-400">
              {sending ? 'Waiting for detections...' : 'Start streaming to see events'}
            </p>
          ) : (
            <div className="space-y-2 max-h-96 overflow-y-auto">
              {eventLog.map((evt, i) => (
                <div
                  key={i}
                  className={`text-xs p-2 rounded-lg ${
                    evt.type === 'compliant'
                      ? 'bg-green-50 text-green-700 border border-green-200'
                      : 'bg-red-50 text-red-700 border border-red-200'
                  }`}
                >
                  <span className="text-slate-400">{evt.time}</span> {evt.text}
                </div>
              ))}
            </div>
          )}

          {/* Person details */}
          {detection && detection.persons.length > 0 && (
            <div className="mt-4 pt-4 border-t border-slate-200 dark:border-slate-700">
              <h4 className="text-xs font-semibold text-slate-500 dark:text-slate-400 mb-2 uppercase">Active Persons</h4>
              <div className="space-y-2">
                {detection.persons.map((p) => (
                  <div key={p.track_id} className="flex items-center justify-between text-xs">
                    <span className="font-medium text-slate-700 dark:text-slate-300">Person #{p.track_id}</span>
                    <div className="flex items-center gap-2">
                      {p.zone && (
                        <span className="px-1.5 py-0.5 bg-slate-100 text-slate-600 rounded">
                          {p.zone}
                        </span>
                      )}
                      <span className={`px-1.5 py-0.5 rounded font-medium ${
                        p.state === 'CLEAN' ? 'bg-green-100 text-green-700' :
                        p.state === 'CONTAMINATED' || p.state === 'DIRTY' ? 'bg-red-100 text-red-700' :
                        'bg-yellow-100 text-yellow-700'
                      }`}>
                        {p.state}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Info */}
      <div className="bg-brand-50 dark:bg-brand-950/30 border border-brand-100 dark:border-brand-900 rounded-xl p-4 text-sm text-brand-700 dark:text-brand-300">
        <strong>How it works:</strong> Start the camera, then click "Stream to Server" to send frames
        to the backend at 2 FPS via WebSocket. The CV pipeline runs YOLOv8 person detection,
        MediaPipe hand tracking, gesture classification, and zone monitoring on each frame.
        Detection results are overlaid on the video and compliance events are published to the dashboard.
      </div>
    </div>
  )
}
