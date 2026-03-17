import { useEffect, useState } from 'react'
import { API_URL } from '../config'
import { authHeaders } from '../utils/api'
import Card from '../components/Card'
import { TrendingUp, AlertTriangle, Users } from 'lucide-react'
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
} from 'recharts'

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
        fetch(`${API_URL}/api/v1/analytics/trends?days=${days}`, { headers: authHeaders() }),
        fetch(`${API_URL}/api/v1/analytics/violations?days=${days}`, { headers: authHeaders() })
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

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="flex items-center gap-3 text-slate-400">
          <div className="w-5 h-5 border-2 border-brand-400 border-t-transparent rounded-full animate-spin" />
          <span className="text-sm">Loading analytics...</span>
        </div>
      </div>
    )
  }

  const avgCompliance = trends.length > 0
    ? trends.reduce((acc, t) => acc + t.compliance_rate, 0) / trends.length
    : 0

  const totalEntries = trends.reduce((acc, t) => acc + t.total_entries, 0)
  const totalViolations = violations.reduce((acc, v) => acc + v.count, 0)

  const trendChartData = trends.map((t) => ({
    date: new Date(t.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
    compliance: parseFloat((t.compliance_rate * 100).toFixed(1)),
  }))

  const violationChartData = violations.map((v) => ({
    name: v.type.replace(/_/g, ' '),
    count: v.count,
    percentage: parseFloat(v.percentage.toFixed(1)),
  }))

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white dark:text-white">Analytics</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-0.5">Compliance trends and violation analysis</p>
        </div>
        <div className="flex items-center gap-1 bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 shadow-card dark:shadow-none p-1">
          {[7, 14, 30].map((d) => (
            <button
              key={d}
              type="button"
              onClick={() => setDays(d)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                days === d
                  ? 'bg-brand-600 text-white shadow-sm'
                  : 'text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-700'
              }`}
            >
              {d}d
            </button>
          ))}
        </div>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card hover>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-brand-50 ring-1 ring-brand-100 flex items-center justify-center">
              <TrendingUp className="w-5 h-5 text-brand-600" />
            </div>
            <div>
              <p className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wide">Avg Compliance</p>
              <p className="text-2xl font-bold text-slate-900 dark:text-white">{(avgCompliance * 100).toFixed(1)}%</p>
            </div>
          </div>
        </Card>
        <Card hover>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-blue-50 ring-1 ring-blue-100 flex items-center justify-center">
              <Users className="w-5 h-5 text-blue-600" />
            </div>
            <div>
              <p className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wide">Total Entries</p>
              <p className="text-2xl font-bold text-slate-900 dark:text-white">{totalEntries}</p>
            </div>
          </div>
        </Card>
        <Card hover>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-red-50 ring-1 ring-red-100 flex items-center justify-center">
              <AlertTriangle className="w-5 h-5 text-red-500" />
            </div>
            <div>
              <p className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wide">Total Violations</p>
              <p className="text-2xl font-bold text-red-600">{totalViolations}</p>
            </div>
          </div>
        </Card>
      </div>

      {/* Compliance Trend */}
      <Card>
        <h2 className="text-base font-semibold text-slate-900 dark:text-white mb-5">Compliance Trend</h2>
        {trendChartData.length > 0 ? (
          <ResponsiveContainer width="100%" height={280}>
            <AreaChart data={trendChartData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="complianceFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#09c4ae" stopOpacity={0.2} />
                  <stop offset="95%" stopColor="#09c4ae" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis
                dataKey="date"
                tick={{ fontSize: 11, fill: '#94a3b8' }}
                tickLine={false}
                axisLine={{ stroke: '#f1f5f9' }}
              />
              <YAxis
                domain={[0, 100]}
                tick={{ fontSize: 11, fill: '#94a3b8' }}
                tickLine={false}
                axisLine={{ stroke: '#f1f5f9' }}
                tickFormatter={(value: number) => `${value}%`}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#fff',
                  border: '1px solid #e2e8f0',
                  borderRadius: '12px',
                  fontSize: '12px',
                  boxShadow: '0 4px 12px rgb(0 0 0 / 0.06)',
                }}
                formatter={(value: number) => [`${value}%`, 'Compliance']}
              />
              <Area
                type="monotone"
                dataKey="compliance"
                stroke="#087e74"
                strokeWidth={2.5}
                fill="url(#complianceFill)"
              />
            </AreaChart>
          </ResponsiveContainer>
        ) : (
          <p className="text-sm text-slate-400 text-center py-12">No trend data available</p>
        )}
      </Card>

      {/* Top Violations */}
      <Card>
        <h2 className="text-base font-semibold text-slate-900 dark:text-white mb-5">Top Violation Types</h2>
        {violationChartData.length > 0 ? (
          <ResponsiveContainer width="100%" height={Math.max(200, violationChartData.length * 50)}>
            <BarChart
              data={violationChartData}
              layout="vertical"
              margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" horizontal={false} />
              <XAxis
                type="number"
                tick={{ fontSize: 11, fill: '#94a3b8' }}
                tickLine={false}
                axisLine={{ stroke: '#f1f5f9' }}
              />
              <YAxis
                type="category"
                dataKey="name"
                tick={{ fontSize: 11, fill: '#475569' }}
                tickLine={false}
                axisLine={{ stroke: '#f1f5f9' }}
                width={140}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#fff',
                  border: '1px solid #e2e8f0',
                  borderRadius: '12px',
                  fontSize: '12px',
                  boxShadow: '0 4px 12px rgb(0 0 0 / 0.06)',
                }}
                formatter={(value: number, _name: string, props: any) => [
                  `${value} (${props.payload.percentage}%)`,
                  'Violations',
                ]}
              />
              <Bar dataKey="count" fill="#ef4444" radius={[0, 6, 6, 0]} barSize={22} />
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <p className="text-sm text-slate-400 text-center py-12">No violation data available</p>
        )}
      </Card>
    </div>
  )
}
