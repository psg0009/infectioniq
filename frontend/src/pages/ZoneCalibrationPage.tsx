import { useState, useRef, useCallback } from 'react'
import { Camera, Save, RotateCcw } from 'lucide-react'
import { API_URL } from '../config'
import { authHeaders } from '../utils/api'

interface Point {
  x: number
  y: number
}

interface ZoneConfig {
  name: string
  color: string
  polygon: Point[]
}

const ZONE_COLORS: Record<string, string> = {
  CRITICAL: '#ef4444',
  STERILE: '#3b82f6',
  NON_STERILE: '#f59e0b',
  SANITIZER: '#22c55e',
  DOOR: '#8b5cf6',
}

const DEFAULT_ZONES: ZoneConfig[] = [
  { name: 'CRITICAL', color: ZONE_COLORS.CRITICAL, polygon: [] },
  { name: 'STERILE', color: ZONE_COLORS.STERILE, polygon: [] },
  { name: 'NON_STERILE', color: ZONE_COLORS.NON_STERILE, polygon: [] },
  { name: 'SANITIZER', color: ZONE_COLORS.SANITIZER, polygon: [] },
  { name: 'DOOR', color: ZONE_COLORS.DOOR, polygon: [] },
]

export default function ZoneCalibrationPage() {
  const [zones, setZones] = useState<ZoneConfig[]>(DEFAULT_ZONES)
  const [activeZone, setActiveZone] = useState<number>(0)
  const [saved, setSaved] = useState(false)
  const [cameraId, setCameraId] = useState('cam-OR-1')
  const canvasRef = useRef<HTMLDivElement>(null)

  const handleCanvasClick = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      const rect = e.currentTarget.getBoundingClientRect()
      const x = (e.clientX - rect.left) / rect.width
      const y = (e.clientY - rect.top) / rect.height

      setZones((prev) => {
        const updated = [...prev]
        updated[activeZone] = {
          ...updated[activeZone],
          polygon: [...updated[activeZone].polygon, { x, y }],
        }
        return updated
      })
      setSaved(false)
    },
    [activeZone]
  )

  const clearZone = (index: number) => {
    setZones((prev) => {
      const updated = [...prev]
      updated[index] = { ...updated[index], polygon: [] }
      return updated
    })
    setSaved(false)
  }

  const handleSave = async () => {
    const config: Record<string, { polygon: number[][] }> = {}
    zones.forEach((zone) => {
      config[zone.name] = {
        polygon: zone.polygon.map((p) => [p.x, p.y]),
      }
    })
    try {
      const res = await fetch(`${API_URL}/api/v1/cameras/${cameraId}/config`, {
        method: 'PUT',
        headers: { ...authHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ zones: config }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      setSaved(true)
    } catch (err) {
      console.error('Failed to save zone config:', err)
      alert('Failed to save zone configuration. Check your connection.')
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Zone Calibration</h1>
          <p className="text-slate-500 dark:text-slate-400 mt-1">Click on the camera view to define zone boundaries</p>
        </div>
        <div className="flex items-center gap-3">
          <select
            value={cameraId}
            onChange={(e) => { setCameraId(e.target.value); setSaved(false) }}
            title="Select camera"
            className="border border-slate-300 dark:border-slate-600 dark:bg-slate-700 dark:text-white rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500"
          >
            {['OR-1', 'OR-2', 'OR-3', 'OR-4', 'OR-5', 'OR-6', 'OR-7', 'OR-8'].map(or => (
              <option key={or} value={`cam-${or}`}>{or}</option>
            ))}
          </select>
          <button
            type="button"
            onClick={handleSave}
            className="flex items-center gap-2 px-4 py-2 bg-gradient-brand text-white rounded-xl hover:opacity-90 shadow-glow-brand font-semibold"
          >
            <Save className="w-4 h-4" />
            {saved ? 'Saved' : 'Save Configuration'}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-4 gap-6">
        {/* Canvas */}
        <div className="col-span-3">
          <div
            ref={canvasRef}
            onClick={handleCanvasClick}
            className="relative w-full aspect-video bg-slate-800 rounded-xl overflow-hidden cursor-crosshair border-2 border-slate-300"
          >
            <div className="absolute inset-0 flex items-center justify-center text-slate-500">
              <Camera className="w-12 h-12 mr-3 opacity-30" />
              <span className="text-lg opacity-50">Camera Feed Area</span>
            </div>

            {/* Draw polygons */}
            <svg className="absolute inset-0 w-full h-full">
              {zones.map((zone, zi) => {
                if (zone.polygon.length < 2) return null
                const points = zone.polygon.map((p) => `${p.x * 100}%,${p.y * 100}%`).join(' ')
                return (
                  <polygon
                    key={zi}
                    points={points}
                    fill={zone.color}
                    fillOpacity={zi === activeZone ? 0.3 : 0.15}
                    stroke={zone.color}
                    strokeWidth="2"
                  />
                )
              })}
              {/* Draw points for active zone */}
              {zones[activeZone]?.polygon.map((p, pi) => (
                <circle
                  key={pi}
                  cx={`${p.x * 100}%`}
                  cy={`${p.y * 100}%`}
                  r="5"
                  fill={zones[activeZone].color}
                  stroke="white"
                  strokeWidth="2"
                />
              ))}
            </svg>
          </div>
        </div>

        {/* Zone list */}
        <div className="space-y-3">
          <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider">Zones</h3>
          {zones.map((zone, index) => (
            <div
              key={zone.name}
              onClick={() => setActiveZone(index)}
              className={`p-3 rounded-lg border-2 cursor-pointer transition-colors ${
                index === activeZone
                  ? 'border-brand-500 bg-brand-50 dark:bg-brand-950/30'
                  : 'border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-800 hover:border-slate-300 dark:hover:border-slate-500'
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full" style={{ backgroundColor: zone.color }} />
                  <span className="text-sm font-medium dark:text-white">{zone.name}</span>
                </div>
                <button
                  type="button"
                  title="Clear zone"
                  onClick={(e) => {
                    e.stopPropagation()
                    clearZone(index)
                  }}
                  className="text-slate-400 hover:text-red-500"
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                </button>
              </div>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                {zone.polygon.length} points
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
