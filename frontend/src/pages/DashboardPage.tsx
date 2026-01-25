import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Activity, AlertTriangle, Users, Droplets, TrendingUp, Clock } from 'lucide-react'
import { useAppStore } from '../stores/appStore'
import type { DashboardMetrics, SurgicalCase, Alert } from '../types'

const API_URL = import.meta.env.VITE_API_URL || ''

export default function DashboardPage() {
  const { metrics, setMetrics, activeCases, setActiveCases, alerts, addAlert } = useAppStore()
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchDashboardData()
    const interval = setInterval(fetchDashboardData, 30000)
    return () => clearInterval(interval)
  }, [])

  const fetchDashboardData = async () => {
    try {
      const [metricsRes, casesRes, alertsRes] = await Promise.all([
        fetch(`${API_URL}/api/v1/analytics/dashboard`),
        fetch(`${API_URL}/api/v1/cases/active`),
        fetch(`${API_URL}/api/v1/alerts/active`)
      ])
      
      if (metricsRes.ok) setMetrics(await metricsRes.json())
      if (casesRes.ok) setActiveCases(await casesRes.json())
    } catch (err) {
      console.error('Failed to fetch dashboard data:', err)
    } finally {
      setLoading(false)
    }
  }

  const getRiskColor = (level: string) => {
    const colors: Record<string, string> = {
      LOW: 'text-green-600 bg-green-50',
      MODERATE: 'text-yellow-600 bg-yellow-50',
      HIGH: 'text-orange-600 bg-orange-50',
      CRITICAL: 'text-red-600 bg-red-50'
    }
    return colors[level] || 'text-slate-600 bg-slate-50'
  }

  if (loading) {
    return <div className="flex items-center justify-center h-64">Loading...</div>
  }

  return (
    <div className="space-y-6">
      {/* Metrics Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="Active Surgeries"
          value={metrics?.active_cases || 0}
          icon={Activity}
          color="blue"
        />
        <MetricCard
          title="Compliance Rate"
          value={`${((metrics?.overall_compliance_rate || 0) * 100).toFixed(1)}%`}
          icon={TrendingUp}
          color="green"
        />
        <MetricCard
          title="Active Alerts"
          value={metrics?.active_alerts || 0}
          icon={AlertTriangle}
          color={metrics?.critical_alerts ? 'red' : 'yellow'}
          subtitle={metrics?.critical_alerts ? `${metrics.critical_alerts} critical` : undefined}
        />
        <MetricCard
          title="Dispensers Low"
          value={metrics?.dispensers_low || 0}
          icon={Droplets}
          color={metrics?.dispensers_low ? 'orange' : 'slate'}
        />
      </div>

      {/* Active Cases & Alerts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Active Cases */}
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
          <h2 className="text-lg font-semibold text-slate-900 mb-4">Active Surgeries</h2>
          <div className="space-y-3">
            {activeCases.length === 0 ? (
              <p className="text-slate-500 text-center py-8">No active surgeries</p>
            ) : (
              activeCases.map(c => (
                <Link
                  key={c.id}
                  to={`/case/${c.id}`}
                  className="block p-4 rounded-lg border border-slate-200 hover:border-blue-300 hover:bg-blue-50 transition-colors"
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-medium text-slate-900">{c.or_number}</p>
                      <p className="text-sm text-slate-500">{c.procedure_type}</p>
                    </div>
                    {c.risk_score && (
                      <span className={`px-3 py-1 rounded-full text-sm font-medium ${getRiskColor(c.risk_score.risk_level)}`}>
                        Risk: {c.risk_score.score}
                      </span>
                    )}
                  </div>
                </Link>
              ))
            )}
          </div>
        </div>

        {/* Recent Alerts */}
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
          <h2 className="text-lg font-semibold text-slate-900 mb-4">Recent Alerts</h2>
          <div className="space-y-3 max-h-80 overflow-y-auto">
            {alerts.filter(a => !a.acknowledged).length === 0 ? (
              <p className="text-slate-500 text-center py-8">No active alerts</p>
            ) : (
              alerts.filter(a => !a.acknowledged).slice(0, 10).map(alert => (
                <div
                  key={alert.id}
                  className={`p-3 rounded-lg border ${
                    alert.severity === 'CRITICAL' 
                      ? 'border-red-300 bg-red-50 alert-critical' 
                      : 'border-yellow-300 bg-yellow-50'
                  }`}
                >
                  <div className="flex items-start gap-2">
                    <AlertTriangle className={`w-5 h-5 mt-0.5 ${
                      alert.severity === 'CRITICAL' ? 'text-red-600' : 'text-yellow-600'
                    }`} />
                    <div>
                      <p className="text-sm font-medium text-slate-900">{alert.message}</p>
                      <p className="text-xs text-slate-500 mt-1">
                        {new Date(alert.timestamp).toLocaleTimeString()}
                      </p>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

function MetricCard({ title, value, icon: Icon, color, subtitle }: {
  title: string
  value: string | number
  icon: any
  color: string
  subtitle?: string
}) {
  const colors: Record<string, string> = {
    blue: 'bg-blue-50 text-blue-600',
    green: 'bg-green-50 text-green-600',
    yellow: 'bg-yellow-50 text-yellow-600',
    orange: 'bg-orange-50 text-orange-600',
    red: 'bg-red-50 text-red-600',
    slate: 'bg-slate-50 text-slate-600',
  }

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-slate-500">{title}</p>
          <p className="text-2xl font-bold text-slate-900 mt-1">{value}</p>
          {subtitle && <p className="text-xs text-red-600 mt-1">{subtitle}</p>}
        </div>
        <div className={`p-3 rounded-lg ${colors[color]}`}>
          <Icon className="w-6 h-6" />
        </div>
      </div>
    </div>
  )
}
