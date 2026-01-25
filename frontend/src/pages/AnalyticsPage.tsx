import { useEffect, useState } from 'react'
import { TrendingUp, TrendingDown, Calendar } from 'lucide-react'

const API_URL = import.meta.env.VITE_API_URL || ''

export default function AnalyticsPage() {
  const [trends, setTrends] = useState<any[]>([])
  const [violations, setViolations] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [days, setDays] = useState(7)

  useEffect(() => {
    fetchAnalytics()
  }, [days])

  const fetchAnalytics = async () => {
    try {
      const [trendsRes, violationsRes] = await Promise.all([
        fetch(`${API_URL}/api/v1/analytics/trends?days=${days}`),
        fetch(`${API_URL}/api/v1/analytics/violations?days=${days}`)
      ])
      if (trendsRes.ok) {
        const data = await trendsRes.json()
        setTrends(data.trends || [])
      }
      if (violationsRes.ok) {
        const data = await violationsRes.json()
        setViolations(data.violations || [])
      }
    } catch (err) {
      console.error('Failed to fetch analytics:', err)
    } finally {
      setLoading(false)
    }
  }

  if (loading) return <div className="text-center py-12">Loading analytics...</div>

  const avgCompliance = trends.length > 0 
    ? trends.reduce((acc, t) => acc + t.compliance_rate, 0) / trends.length 
    : 0

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-900">Analytics</h1>
        <select
          value={days}
          onChange={(e) => setDays(Number(e.target.value))}
          className="px-4 py-2 border border-slate-300 rounded-lg bg-white"
        >
          <option value={7}>Last 7 days</option>
          <option value={14}>Last 14 days</option>
          <option value={30}>Last 30 days</option>
        </select>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
          <p className="text-sm text-slate-500">Average Compliance</p>
          <p className="text-3xl font-bold text-slate-900 mt-1">
            {(avgCompliance * 100).toFixed(1)}%
          </p>
        </div>
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
          <p className="text-sm text-slate-500">Total Entries</p>
          <p className="text-3xl font-bold text-slate-900 mt-1">
            {trends.reduce((acc, t) => acc + t.total_entries, 0)}
          </p>
        </div>
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
          <p className="text-sm text-slate-500">Total Violations</p>
          <p className="text-3xl font-bold text-red-600 mt-1">
            {violations.reduce((acc, v) => acc + v.count, 0)}
          </p>
        </div>
      </div>

      {/* Compliance Trend */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
        <h2 className="text-lg font-semibold mb-4">Compliance Trend</h2>
        <div className="h-64 flex items-end gap-2">
          {trends.map((t, i) => (
            <div key={i} className="flex-1 flex flex-col items-center">
              <div 
                className="w-full bg-blue-500 rounded-t"
                style={{ height: `${t.compliance_rate * 100 * 2}px` }}
              />
              <p className="text-xs text-slate-500 mt-2 rotate-45 origin-left">
                {new Date(t.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
              </p>
            </div>
          ))}
        </div>
      </div>

      {/* Top Violations */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
        <h2 className="text-lg font-semibold mb-4">Top Violation Types</h2>
        <div className="space-y-3">
          {violations.map((v, i) => (
            <div key={i} className="flex items-center gap-4">
              <div className="flex-1">
                <p className="font-medium text-slate-900">{v.type.replace(/_/g, ' ')}</p>
                <div className="h-2 bg-slate-100 rounded-full mt-1">
                  <div 
                    className="h-full bg-red-500 rounded-full"
                    style={{ width: `${v.percentage}%` }}
                  />
                </div>
              </div>
              <span className="text-sm text-slate-500">{v.count} ({v.percentage.toFixed(1)}%)</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
