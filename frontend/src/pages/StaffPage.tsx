import { useState, useEffect } from 'react'
import { Search, AlertCircle } from 'lucide-react'
import { apiFetch } from '../utils/api'
import type { Staff } from '../types'

export default function StaffPage() {
  const [staff, setStaff] = useState<Staff[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [search, setSearch] = useState('')

  useEffect(() => {
    apiFetch<{ staff: Staff[] }>('/api/v1/staff/')
      .then((data) => setStaff(data.staff || []))
      .catch((err) => setError(err.message || 'Failed to load staff'))
      .finally(() => setLoading(false))
  }, [])

  const filtered = staff.filter(
    (s) =>
      s.name.toLowerCase().includes(search.toLowerCase()) ||
      s.employee_id.toLowerCase().includes(search.toLowerCase())
  )

  const roleColor = (role: string) => {
    const colors: Record<string, string> = {
      SURGEON: 'bg-blue-100 text-blue-700',
      NURSE: 'bg-green-100 text-green-700',
      ANESTHESIOLOGIST: 'bg-purple-100 text-purple-700',
      TECHNICIAN: 'bg-amber-100 text-amber-700',
      RESIDENT: 'bg-slate-100 text-slate-700',
    }
    return colors[role] || 'bg-slate-100 text-slate-700'
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Staff Management</h1>
          <p className="text-slate-500 dark:text-slate-400 mt-1">{staff.length} staff members</p>
        </div>
      </div>

      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
        <input
          type="text"
          placeholder="Search by name or ID..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full pl-10 pr-4 py-2.5 bg-white dark:bg-slate-700 border border-slate-200 dark:border-slate-600 dark:text-white rounded-xl shadow-card dark:shadow-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 outline-none transition-all"
        />
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-center gap-3">
          <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0" />
          <span className="text-red-700 text-sm">{error}</span>
        </div>
      )}

      {loading ? (
        <div className="text-center py-12 text-slate-500 dark:text-slate-400">Loading staff...</div>
      ) : !error ? (
        <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-card dark:shadow-none border border-slate-100 dark:border-slate-700 overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="bg-slate-50/70 dark:bg-slate-800/50 border-b border-slate-100 dark:border-slate-700">
                <th className="px-5 py-3.5 text-left text-[10px] font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">Name</th>
                <th className="px-5 py-3.5 text-left text-[10px] font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">Employee ID</th>
                <th className="px-5 py-3.5 text-left text-[10px] font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">Role</th>
                <th className="px-5 py-3.5 text-left text-[10px] font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">Department</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((member) => (
                <tr key={member.id} className="border-b border-slate-50 dark:border-slate-700 hover:bg-brand-50/20 dark:hover:bg-brand-950/20 transition-colors">
                  <td className="px-5 py-3.5">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 bg-brand-100 dark:bg-brand-900 rounded-lg flex items-center justify-center">
                        <span className="text-xs font-bold text-brand-700 dark:text-brand-300">{member.name[0]}</span>
                      </div>
                      <span className="text-sm font-medium text-slate-900 dark:text-white">{member.name}</span>
                    </div>
                  </td>
                  <td className="px-5 py-3.5 text-sm text-slate-500 dark:text-slate-400 font-mono">{member.employee_id}</td>
                  <td className="px-5 py-3.5">
                    <span className={`text-[11px] font-semibold px-2.5 py-1 rounded-lg ${roleColor(member.role)}`}>
                      {member.role}
                    </span>
                  </td>
                  <td className="px-5 py-3.5 text-sm text-slate-500 dark:text-slate-400">{member.department || '—'}</td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={4} className="px-4 py-8 text-center text-slate-500 dark:text-slate-400">
                    No staff found
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  )
}
