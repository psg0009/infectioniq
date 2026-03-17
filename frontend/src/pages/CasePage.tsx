import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { ArrowLeft, Activity } from 'lucide-react'
import type { SurgicalCase } from '../types'
import { API_URL } from '../config'
import { authHeaders } from '../utils/api'
import { getRiskBgColor } from '../utils/colors'
import Card from '../components/Card'

export default function CasePage() {
  const { caseId } = useParams()
  const [caseData, setCaseData] = useState<SurgicalCase | null>(null)
  const [compliance, setCompliance] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (caseId) fetchCaseData()
  }, [caseId])

  const fetchCaseData = async () => {
    try {
      const [caseRes, complianceRes] = await Promise.all([
        fetch(`${API_URL}/api/v1/cases/${caseId}`, { headers: authHeaders() }),
        fetch(`${API_URL}/api/v1/cases/${caseId}/compliance`, { headers: authHeaders() })
      ])
      if (caseRes.ok) setCaseData(await caseRes.json())
      if (complianceRes.ok) setCompliance(await complianceRes.json())
    } catch (err) {
      console.error('Failed to fetch case data:', err)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="flex items-center gap-3 text-slate-400">
          <div className="w-5 h-5 border-2 border-brand-400 border-t-transparent rounded-full animate-spin" />
          <span className="text-sm">Loading case...</span>
        </div>
      </div>
    )
  }
  if (!caseData) return <div className="text-center py-12 text-slate-500">Case not found</div>

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link to="/" className="p-2 rounded-xl hover:bg-slate-100 transition-colors">
          <ArrowLeft className="w-5 h-5 text-slate-500" />
        </Link>
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-brand-50 ring-1 ring-brand-100 flex items-center justify-center">
            <Activity className="w-5 h-5 text-brand-600" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-slate-900 dark:text-white">{caseData.or_number}</h1>
            <p className="text-sm text-slate-500 dark:text-slate-400">{caseData.procedure_type}</p>
          </div>
        </div>
      </div>

      {/* Risk Score */}
      {caseData.risk_score && (
        <Card>
          <h2 className="text-base font-semibold text-slate-900 dark:text-white mb-5">Risk Assessment</h2>
          <div className="flex items-center gap-6">
            <div className={`w-20 h-20 rounded-2xl flex items-center justify-center ${getRiskBgColor(caseData.risk_score.risk_level)}`}>
              <span className="text-2xl font-extrabold text-white">{caseData.risk_score.score}</span>
            </div>
            <div className="flex-1">
              <p className="text-lg font-semibold text-slate-900">{caseData.risk_score.risk_level} Risk</p>
              <div className="mt-2 space-y-1">
                {caseData.risk_score.factors?.slice(0, 3).map((f, i) => (
                  <p key={i} className="text-sm text-slate-500 dark:text-slate-400">{f.description}</p>
                ))}
              </div>
            </div>
          </div>
        </Card>
      )}

      {/* Compliance */}
      {compliance && (
        <Card>
          <h2 className="text-base font-semibold text-slate-900 dark:text-white mb-5">Compliance Status</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="text-center p-4 bg-brand-50/50 rounded-xl border border-brand-100">
              <p className="text-2xl font-bold text-slate-900 dark:text-white">
                {(compliance.overall_compliance_rate * 100).toFixed(0)}%
              </p>
              <p className="text-xs text-slate-500 mt-1 font-medium">Compliance Rate</p>
            </div>
            <div className="text-center p-4 bg-slate-50 rounded-xl border border-slate-100">
              <p className="text-2xl font-bold text-slate-900 dark:text-white">{compliance.total_entries}</p>
              <p className="text-xs text-slate-500 mt-1 font-medium">Total Entries</p>
            </div>
            <div className="text-center p-4 bg-green-50/50 rounded-xl border border-green-100">
              <p className="text-2xl font-bold text-green-600">{compliance.compliant_entries}</p>
              <p className="text-xs text-slate-500 mt-1 font-medium">Compliant</p>
            </div>
            <div className="text-center p-4 bg-red-50/50 rounded-xl border border-red-100">
              <p className="text-2xl font-bold text-red-600">{compliance.alerts_count}</p>
              <p className="text-xs text-slate-500 mt-1 font-medium">Alerts</p>
            </div>
          </div>
        </Card>
      )}
    </div>
  )
}
