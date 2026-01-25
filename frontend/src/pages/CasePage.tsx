import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { ArrowLeft, AlertTriangle, User, Clock, Activity } from 'lucide-react'
import type { SurgicalCase, TouchEvent, Alert } from '../types'

const API_URL = import.meta.env.VITE_API_URL || ''

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
        fetch(`${API_URL}/api/v1/cases/${caseId}`),
        fetch(`${API_URL}/api/v1/cases/${caseId}/compliance`)
      ])
      if (caseRes.ok) setCaseData(await caseRes.json())
      if (complianceRes.ok) setCompliance(await complianceRes.json())
    } catch (err) {
      console.error('Failed to fetch case data:', err)
    } finally {
      setLoading(false)
    }
  }

  const getRiskColor = (level: string) => {
    const colors: Record<string, string> = {
      LOW: 'bg-green-500',
      MODERATE: 'bg-yellow-500',
      HIGH: 'bg-orange-500',
      CRITICAL: 'bg-red-500'
    }
    return colors[level] || 'bg-slate-500'
  }

  if (loading) return <div className="text-center py-12">Loading...</div>
  if (!caseData) return <div className="text-center py-12">Case not found</div>

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link to="/" className="p-2 rounded-lg hover:bg-slate-200">
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <div>
          <h1 className="text-2xl font-bold text-slate-900">{caseData.or_number}</h1>
          <p className="text-slate-500">{caseData.procedure_type}</p>
        </div>
      </div>

      {/* Risk Score */}
      {caseData.risk_score && (
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
          <h2 className="text-lg font-semibold mb-4">Risk Assessment</h2>
          <div className="flex items-center gap-6">
            <div className={`w-24 h-24 rounded-full flex items-center justify-center ${getRiskColor(caseData.risk_score.risk_level)}`}>
              <span className="text-3xl font-bold text-white">{caseData.risk_score.score}</span>
            </div>
            <div className="flex-1">
              <p className="text-xl font-semibold">{caseData.risk_score.risk_level} Risk</p>
              <div className="mt-2 space-y-1">
                {caseData.risk_score.factors?.slice(0, 3).map((f, i) => (
                  <p key={i} className="text-sm text-slate-600">• {f.description}</p>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Compliance */}
      {compliance && (
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
          <h2 className="text-lg font-semibold mb-4">Compliance Status</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="text-center p-4 bg-slate-50 rounded-lg">
              <p className="text-2xl font-bold text-slate-900">
                {(compliance.overall_compliance_rate * 100).toFixed(0)}%
              </p>
              <p className="text-sm text-slate-500">Compliance Rate</p>
            </div>
            <div className="text-center p-4 bg-slate-50 rounded-lg">
              <p className="text-2xl font-bold text-slate-900">{compliance.total_entries}</p>
              <p className="text-sm text-slate-500">Total Entries</p>
            </div>
            <div className="text-center p-4 bg-slate-50 rounded-lg">
              <p className="text-2xl font-bold text-green-600">{compliance.compliant_entries}</p>
              <p className="text-sm text-slate-500">Compliant</p>
            </div>
            <div className="text-center p-4 bg-slate-50 rounded-lg">
              <p className="text-2xl font-bold text-red-600">{compliance.alerts_count}</p>
              <p className="text-sm text-slate-500">Alerts</p>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
