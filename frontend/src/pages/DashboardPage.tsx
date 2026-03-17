import { useEffect, useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { Activity, AlertTriangle, Droplets, TrendingUp, ArrowUpRight, Clock } from 'lucide-react'
import { useAppStore } from '../stores/appStore'
import { API_URL } from '../config'
import { authHeaders } from '../utils/api'
import { getRiskBadgeColor } from '../utils/colors'
import { useWebSocket } from '../hooks/useWebSocket'
import Card from '../components/Card'

// SVG ring gauge for compliance rate
function ComplianceRing({ rate }: { rate: number }) {
  const pct = Math.round(rate * 100)
  const radius = 54
  const circumference = 2 * Math.PI * radius
  const offset = circumference - (rate * circumference)
  const color = pct >= 80 ? '#10b981' : pct >= 60 ? '#f59e0b' : '#ef4444'

  return (
    <div className="relative w-36 h-36 mx-auto">
      <svg viewBox="0 0 128 128" className="w-full h-full -rotate-90">
        <circle cx="64" cy="64" r={radius} fill="none" className="stroke-slate-100 dark:stroke-slate-700" strokeWidth="10" />
        <circle
          cx="64" cy="64" r={radius} fill="none"
          stroke={color} strokeWidth="10" strokeLinecap="round"
          strokeDasharray={circumference} strokeDashoffset={offset}
          className="transition-all duration-700 ease-out"
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-3xl font-extrabold text-slate-900 dark:text-white">{pct}%</span>
        <span className="text-[10px] font-medium text-slate-400 dark:text-slate-500 uppercase tracking-wider">Compliance</span>
      </div>
    </div>
  )
}

export default function DashboardPage() {
  const { metrics, setMetrics, activeCases, setActiveCases, alerts, setAlerts, addAlert } = useAppStore()
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const handleWsMessage = useCallback((data: unknown) => {
    const alert = data as any
    if (alert && alert.id && alert.message) {
      addAlert(alert)
    }
  }, [addAlert])

  useWebSocket('/alerts', { onMessage: handleWsMessage })

  useEffect(() => {
    fetchDashboardData()
    const interval = setInterval(fetchDashboardData, 30000)
    return () => clearInterval(interval)
  }, [])

  const fetchDashboardData = async () => {
    try {
      setError(null)
      const [metricsRes, casesRes, alertsRes] = await Promise.all([
        fetch(`${API_URL}/api/v1/analytics/dashboard`, { headers: authHeaders() }),
        fetch(`${API_URL}/api/v1/cases/active`, { headers: authHeaders() }),
        fetch(`${API_URL}/api/v1/alerts/active`, { headers: authHeaders() })
      ])
      if (metricsRes.ok) setMetrics(await metricsRes.json())
      if (casesRes.ok) setActiveCases(await casesRes.json())
      if (alertsRes.ok) setAlerts(await alertsRes.json())
    } catch (err) {
      console.error('Failed to fetch dashboard data:', err)
      setError('Failed to load dashboard data.')
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="flex items-center gap-3 text-slate-400">
          <div className="w-5 h-5 border-2 border-brand-400 border-t-transparent rounded-full animate-spin" />
          <span className="text-sm">Loading dashboard...</span>
        </div>
      </div>
    )
  }

  const complianceRate = metrics?.overall_compliance_rate || 0
  const todayEntries = metrics?.today_entries || 0
  const todayViolations = metrics?.today_violations || 0
  const unacknowledgedAlerts = alerts.filter(a => !a.acknowledged)

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Dashboard</h1>
        <p className="text-sm text-slate-500 dark:text-slate-400 mt-0.5">Real-time surgical infection prevention monitoring</p>
      </div>

      {error && (
        <div className="bg-red-50 dark:bg-red-950/40 border border-red-100 dark:border-red-800 text-red-700 dark:text-red-300 px-4 py-3 rounded-xl text-sm">
          {error}
        </div>
      )}

      {/* Top metrics row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 animate-fade-in-up">
        <MetricCard
          label="Active Surgeries"
          value={metrics?.active_cases || 0}
          icon={Activity}
          accent="brand"
        />
        <MetricCard
          label="Today's Entries"
          value={todayEntries}
          icon={TrendingUp}
          accent="blue"
        />
        <MetricCard
          label="Active Alerts"
          value={metrics?.active_alerts || 0}
          icon={AlertTriangle}
          accent={metrics?.critical_alerts ? 'red' : 'amber'}
          sub={metrics?.critical_alerts ? `${metrics.critical_alerts} critical` : undefined}
        />
        <MetricCard
          label="Dispensers Low"
          value={metrics?.dispensers_low || 0}
          icon={Droplets}
          accent={metrics?.dispensers_low ? 'orange' : 'slate'}
        />
      </div>

      {/* Compliance + entries row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 animate-fade-in-up-delay-1">
        {/* Compliance ring */}
        <Card className="flex flex-col items-center justify-center py-8">
          <ComplianceRing rate={complianceRate} />
          <div className="flex items-center gap-6 mt-5 text-center">
            <div>
              <p className="text-xl font-bold text-slate-900 dark:text-white">{todayEntries - todayViolations}</p>
              <p className="text-[11px] text-green-600 font-medium uppercase tracking-wide">Compliant</p>
            </div>
            <div className="w-px h-8 bg-slate-200 dark:bg-slate-700" />
            <div>
              <p className="text-xl font-bold text-slate-900 dark:text-white">{todayViolations}</p>
              <p className="text-[11px] text-red-500 font-medium uppercase tracking-wide">Violations</p>
            </div>
          </div>
        </Card>

        {/* Active surgeries */}
        <Card className="lg:col-span-2">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-base font-semibold text-slate-900 dark:text-white">Active Surgeries</h2>
            <span className="text-xs text-slate-400 dark:text-slate-500">{activeCases.length} active</span>
          </div>
          <div className="space-y-2">
            {activeCases.length === 0 ? (
              <p className="text-slate-400 text-sm text-center py-10">No active surgeries</p>
            ) : (
              activeCases.map(c => (
                <Link
                  key={c.id}
                  to={`/case/${c.id}`}
                  className="group flex items-center justify-between p-3.5 rounded-xl border border-slate-100 dark:border-slate-700 hover:border-brand-200 dark:hover:border-brand-700 hover:bg-brand-50/30 dark:hover:bg-brand-950/30 transition-all"
                >
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-brand-50 dark:bg-brand-950/50 flex items-center justify-center flex-shrink-0">
                      <Activity className="w-4 h-4 text-brand-600" />
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-slate-900 dark:text-white">{c.or_number}</p>
                      <p className="text-xs text-slate-500 dark:text-slate-400">{c.procedure_type}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    {c.risk_score && (
                      <span className={`px-2.5 py-1 rounded-lg text-xs font-semibold ${getRiskBadgeColor(c.risk_score.risk_level)}`}>
                        Risk {c.risk_score.score}
                      </span>
                    )}
                    <ArrowUpRight className="w-4 h-4 text-slate-300 group-hover:text-brand-500 transition-colors" />
                  </div>
                </Link>
              ))
            )}
          </div>
        </Card>
      </div>

      {/* Alerts */}
      <Card className="animate-fade-in-up-delay-2">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-semibold text-slate-900 dark:text-white">Recent Alerts</h2>
          <span className="text-xs text-slate-400 dark:text-slate-500">{unacknowledgedAlerts.length} unacknowledged</span>
        </div>
        <div className="space-y-2 max-h-80 overflow-y-auto">
          {unacknowledgedAlerts.length === 0 ? (
            <p className="text-slate-400 text-sm text-center py-10">No active alerts</p>
          ) : (
            unacknowledgedAlerts.slice(0, 12).map(alert => (
              <div
                key={alert.id}
                className={`flex items-start gap-3 p-3.5 rounded-xl border transition-colors ${
                  alert.severity === 'CRITICAL'
                    ? 'border-red-200 bg-red-50/60 dark:border-red-800 dark:bg-red-950/40'
                    : alert.severity === 'HIGH'
                    ? 'border-orange-200 bg-orange-50/50 dark:border-orange-800 dark:bg-orange-950/40'
                    : 'border-amber-200 bg-amber-50/50 dark:border-amber-800 dark:bg-amber-950/40'
                }`}
              >
                <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${
                  alert.severity === 'CRITICAL'
                    ? 'bg-red-100 dark:bg-red-900/50'
                    : alert.severity === 'HIGH'
                    ? 'bg-orange-100 dark:bg-orange-900/50'
                    : 'bg-amber-100 dark:bg-amber-900/50'
                }`}>
                  <AlertTriangle className={`w-4 h-4 ${
                    alert.severity === 'CRITICAL' ? 'text-red-600'
                    : alert.severity === 'HIGH' ? 'text-orange-600'
                    : 'text-amber-600'
                  }`} />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-slate-900 dark:text-slate-100">{alert.message}</p>
                  <div className="flex items-center gap-2 mt-1">
                    <Clock className="w-3 h-3 text-slate-400" />
                    <p className="text-xs text-slate-500">
                      {new Date(alert.timestamp).toLocaleTimeString()}
                    </p>
                    {alert.severity === 'CRITICAL' && (
                      <span className="px-1.5 py-0.5 bg-red-600 text-white text-[10px] font-bold rounded uppercase">
                        Critical
                      </span>
                    )}
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </Card>
    </div>
  )
}

function MetricCard({ label, value, icon: Icon, accent, sub }: {
  label: string
  value: string | number
  icon: any
  accent: string
  sub?: string
}) {
  const accents: Record<string, { bg: string; icon: string; ring: string }> = {
    brand:  { bg: 'bg-brand-50 dark:bg-brand-950/50',  icon: 'text-brand-600 dark:text-brand-400',  ring: 'ring-brand-100 dark:ring-brand-800' },
    blue:   { bg: 'bg-blue-50 dark:bg-blue-950/50',   icon: 'text-blue-600 dark:text-blue-400',   ring: 'ring-blue-100 dark:ring-blue-800' },
    green:  { bg: 'bg-green-50 dark:bg-green-950/50',  icon: 'text-green-600 dark:text-green-400',  ring: 'ring-green-100 dark:ring-green-800' },
    amber:  { bg: 'bg-amber-50 dark:bg-amber-950/50',  icon: 'text-amber-600 dark:text-amber-400',  ring: 'ring-amber-100 dark:ring-amber-800' },
    orange: { bg: 'bg-orange-50 dark:bg-orange-950/50', icon: 'text-orange-600 dark:text-orange-400', ring: 'ring-orange-100 dark:ring-orange-800' },
    red:    { bg: 'bg-red-50 dark:bg-red-950/50',    icon: 'text-red-600 dark:text-red-400',    ring: 'ring-red-100 dark:ring-red-800' },
    slate:  { bg: 'bg-slate-50 dark:bg-slate-800',  icon: 'text-slate-500 dark:text-slate-400',  ring: 'ring-slate-100 dark:ring-slate-700' },
  }
  const a = accents[accent] || accents.slate

  return (
    <Card hover>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wide">{label}</p>
          <p className="text-2xl font-bold text-slate-900 dark:text-white mt-1.5">{value}</p>
          {sub && <p className="text-[11px] text-red-500 font-medium mt-0.5">{sub}</p>}
        </div>
        <div className={`w-10 h-10 rounded-xl ${a.bg} ring-1 ${a.ring} flex items-center justify-center`}>
          <Icon className={`w-5 h-5 ${a.icon}`} />
        </div>
      </div>
    </Card>
  )
}
