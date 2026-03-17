import { useState, useEffect } from 'react'
import { Droplets, AlertTriangle, CheckCircle, XCircle, AlertCircle } from 'lucide-react'
import { apiFetch } from '../utils/api'
import type { DispenserStatus } from '../types'

export default function DispensersPage() {
  const [dispensers, setDispensers] = useState<DispenserStatus[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    apiFetch<{ dispensers: DispenserStatus[] }>('/api/v1/dispensers/')
      .then((data) => setDispensers(data.dispensers || []))
      .catch((err) => setError(err.message || 'Failed to load dispensers'))
      .finally(() => setLoading(false))
  }, [])

  const statusIcon = (status: string) => {
    switch (status) {
      case 'OK': return <CheckCircle className="w-4 h-4 text-green-500" />
      case 'WARNING': return <AlertTriangle className="w-4 h-4 text-amber-500" />
      case 'LOW': case 'CRITICAL': return <AlertTriangle className="w-4 h-4 text-red-500" />
      case 'EMPTY': return <XCircle className="w-4 h-4 text-red-600" />
      default: return <Droplets className="w-4 h-4 text-slate-400" />
    }
  }

  const levelColor = (pct: number) => {
    if (pct > 50) return 'bg-green-500'
    if (pct > 25) return 'bg-amber-500'
    return 'bg-red-500'
  }

  const levelBg = (pct: number) => {
    if (pct > 50) return 'bg-green-50 ring-green-100'
    if (pct > 25) return 'bg-amber-50 ring-amber-100'
    return 'bg-red-50 ring-red-100'
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Dispensers</h1>
        <p className="text-sm text-slate-500 dark:text-slate-400 mt-0.5">{dispensers.length} sanitizer dispensers registered</p>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-100 rounded-xl p-4 flex items-center gap-3">
          <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0" />
          <span className="text-red-700 text-sm">{error}</span>
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center h-64">
          <div className="flex items-center gap-3 text-slate-400">
            <div className="w-5 h-5 border-2 border-brand-400 border-t-transparent rounded-full animate-spin" />
            <span className="text-sm">Loading dispensers...</span>
          </div>
        </div>
      ) : !error ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {dispensers.map((d) => (
            <div key={d.dispenser_id} className="bg-white dark:bg-slate-800 rounded-2xl shadow-card dark:shadow-none border border-slate-100 dark:border-slate-700 p-5 hover:shadow-card-hover dark:hover:border-slate-600 transition-all">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className={`w-10 h-10 rounded-xl ${levelBg(d.level_percent)} ring-1 flex items-center justify-center`}>
                    <Droplets className="w-5 h-5 text-brand-600" />
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-slate-900 dark:text-white">{d.dispenser_id}</p>
                    <p className="text-xs text-slate-500 dark:text-slate-400">{d.or_number}</p>
                  </div>
                </div>
                {statusIcon(d.status)}
              </div>

              <div>
                <div className="flex justify-between text-xs mb-1.5">
                  <span className="text-slate-500 dark:text-slate-400 font-medium">Fill Level</span>
                  <span className="font-bold text-slate-900 dark:text-white">{d.level_percent}%</span>
                </div>
                <div className="w-full bg-slate-100 dark:bg-slate-700 rounded-full h-2">
                  <div
                    className={`h-2 rounded-full transition-all duration-500 ${levelColor(d.level_percent)}`}
                    style={{ width: `${d.level_percent}%` }}
                  />
                </div>
              </div>

              {d.days_until_expiration != null && (
                <p className="text-[11px] text-slate-400 mt-3">
                  Expires in <span className="font-medium text-slate-600 dark:text-slate-300">{d.days_until_expiration} days</span>
                </p>
              )}
            </div>
          ))}
          {dispensers.length === 0 && (
            <div className="col-span-full text-center py-12 text-slate-400">
              No dispensers found
            </div>
          )}
        </div>
      ) : null}
    </div>
  )
}
