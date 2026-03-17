import { useState, useEffect, useCallback } from 'react'
import { API_URL } from '../config'
import { authHeaders } from '../utils/api'

interface CalibrationSession {
  id: string
  name: string
  or_number: string | null
  observer_name: string | null
  glove_type: string | null
  total_samples: number
  sanitizing_count: number
  not_sanitizing_count: number
  best_accuracy: number | null
  created_at: string | null
}

interface SweepResult {
  palm_distance_threshold: number
  motion_threshold: number
  oscillation_threshold: number
  score_threshold: number
  accuracy: number
  sensitivity: number
  specificity: number
  tp: number
  tn: number
  fp: number
  fn: number
}

interface ThresholdState {
  palm_distance_threshold: number
  motion_threshold: number
  oscillation_threshold: number
  score_threshold: number
  min_duration_sec: number
}

const DEFAULT_THRESHOLDS: ThresholdState = {
  palm_distance_threshold: 0.15,
  motion_threshold: 0.02,
  oscillation_threshold: 4,
  score_threshold: 0.7,
  min_duration_sec: 3.0,
}

export default function GestureCalibrationPage() {
  const [sessions, setSessions] = useState<CalibrationSession[]>([])
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null)
  const [sweepResults, setSweepResults] = useState<SweepResult[]>([])
  const [sweepBest, setSweepBest] = useState<SweepResult | null>(null)
  const [thresholds, setThresholds] = useState<ThresholdState>(DEFAULT_THRESHOLDS)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [newSessionName, setNewSessionName] = useState('')
  const [newSessionOR, setNewSessionOR] = useState('')
  const [applyProfileName, setApplyProfileName] = useState('')
  const [successMessage, setSuccessMessage] = useState<string | null>(null)

  const fetchSessions = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/v1/calibration/sessions`, { headers: authHeaders() })
      if (res.ok) {
        const data = await res.json()
        setSessions(data.sessions)
      }
    } catch (err) {
      console.error('Failed to fetch sessions', err)
    }
  }, [])

  useEffect(() => {
    fetchSessions()
  }, [fetchSessions])

  const createSession = async () => {
    if (!newSessionName.trim()) return
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${API_URL}/api/v1/calibration/sessions`, {
        method: 'POST',
        headers: { ...authHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: newSessionName,
          or_number: newSessionOR || null,
        }),
      })
      if (res.ok) {
        setNewSessionName('')
        setNewSessionOR('')
        await fetchSessions()
      }
    } catch (err) {
      setError('Failed to create session')
    } finally {
      setLoading(false)
    }
  }

  const runSweep = async (sessionId: string) => {
    setLoading(true)
    setError(null)
    setSweepResults([])
    setSweepBest(null)
    try {
      const res = await fetch(`${API_URL}/api/v1/calibration/sessions/${sessionId}/sweep`, {
        method: 'POST',
        headers: { ...authHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      })
      if (res.ok) {
        const data = await res.json()
        setSweepResults(data.top_10 || [])
        setSweepBest(data.best || null)
        if (data.best) {
          setThresholds({
            palm_distance_threshold: data.best.palm_distance_threshold,
            motion_threshold: data.best.motion_threshold,
            oscillation_threshold: data.best.oscillation_threshold,
            score_threshold: data.best.score_threshold,
            min_duration_sec: thresholds.min_duration_sec,
          })
        }
        setSelectedSessionId(sessionId)
        await fetchSessions()
      } else {
        const errData = await res.json()
        setError(errData.detail || 'Sweep failed')
      }
    } catch (err) {
      setError('Failed to run sweep')
    } finally {
      setLoading(false)
    }
  }

  const applyThresholds = async () => {
    if (!selectedSessionId || !applyProfileName.trim()) return
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${API_URL}/api/v1/calibration/sessions/${selectedSessionId}/apply`, {
        method: 'POST',
        headers: { ...authHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({
          profile_name: applyProfileName,
          palm_distance_threshold: thresholds.palm_distance_threshold,
          motion_threshold: thresholds.motion_threshold,
          oscillation_threshold: thresholds.oscillation_threshold,
          score_threshold: thresholds.score_threshold,
        }),
      })
      if (res.ok) {
        setSuccessMessage('Thresholds applied to profile successfully!')
        setTimeout(() => setSuccessMessage(null), 3000)
      }
    } catch (err) {
      setError('Failed to apply thresholds')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Gesture Calibration</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
            Tune sanitization detection thresholds with labeled samples
          </p>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
          {error}
        </div>
      )}
      {successMessage && (
        <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded-lg">
          {successMessage}
        </div>
      )}

      {/* Create Session */}
      <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-card dark:shadow-none border border-slate-100 dark:border-slate-700 p-6">
        <h2 className="text-lg font-semibold text-slate-900 dark:text-white mb-4">New Calibration Session</h2>
        <div className="flex gap-3 items-end flex-wrap">
          <div>
            <label className="block text-sm font-medium text-slate-600 dark:text-slate-300 mb-1">Session Name</label>
            <input
              type="text"
              value={newSessionName}
              onChange={e => setNewSessionName(e.target.value)}
              className="border border-slate-300 dark:border-slate-600 dark:bg-slate-700 dark:text-white rounded-lg px-3 py-2 text-sm"
              placeholder="e.g. OR-1 Nitrile Gloves"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-600 dark:text-slate-300 mb-1">OR Number</label>
            <input
              type="text"
              value={newSessionOR}
              onChange={e => setNewSessionOR(e.target.value)}
              className="border border-slate-300 dark:border-slate-600 dark:bg-slate-700 dark:text-white rounded-lg px-3 py-2 text-sm"
              placeholder="e.g. OR-1"
            />
          </div>
          <button
            onClick={createSession}
            disabled={loading || !newSessionName.trim()}
            className="bg-gradient-brand text-white px-4 py-2 rounded-xl text-sm font-semibold hover:opacity-90 shadow-glow-brand disabled:opacity-50"
          >
            Create Session
          </button>
        </div>
      </div>

      {/* Sessions Table */}
      <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-card dark:shadow-none border border-slate-100 dark:border-slate-700 p-6">
        <h2 className="text-lg font-semibold text-slate-900 dark:text-white mb-4">Calibration Sessions</h2>
        {sessions.length === 0 ? (
          <p className="text-sm text-slate-500 dark:text-slate-400">No calibration sessions yet. Create one above or upload samples from the CV module.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200 dark:border-slate-700 text-left text-slate-600 dark:text-slate-400">
                  <th className="pb-2 font-medium">Name</th>
                  <th className="pb-2 font-medium">OR</th>
                  <th className="pb-2 font-medium">Samples</th>
                  <th className="pb-2 font-medium">Sanitizing</th>
                  <th className="pb-2 font-medium">Not Sanitizing</th>
                  <th className="pb-2 font-medium">Best Accuracy</th>
                  <th className="pb-2 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {sessions.map(s => (
                  <tr key={s.id} className="border-b border-slate-100 dark:border-slate-700">
                    <td className="py-3 font-medium text-slate-800 dark:text-white">{s.name}</td>
                    <td className="py-3 text-slate-600 dark:text-slate-400">{s.or_number || '-'}</td>
                    <td className="py-3 text-slate-600 dark:text-slate-400">{s.total_samples}</td>
                    <td className="py-3 text-green-600">{s.sanitizing_count}</td>
                    <td className="py-3 text-red-600">{s.not_sanitizing_count}</td>
                    <td className="py-3">
                      {s.best_accuracy !== null ? (
                        <span className={`font-medium ${s.best_accuracy >= 0.9 ? 'text-green-600' : s.best_accuracy >= 0.7 ? 'text-yellow-600' : 'text-red-600'}`}>
                          {(s.best_accuracy * 100).toFixed(1)}%
                        </span>
                      ) : '-'}
                    </td>
                    <td className="py-3">
                      <button
                        onClick={() => runSweep(s.id)}
                        disabled={loading || s.total_samples === 0}
                        className="text-brand-600 hover:text-brand-800 font-medium disabled:opacity-50"
                      >
                        Run Sweep
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Threshold Sliders */}
      <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-card dark:shadow-none border border-slate-100 dark:border-slate-700 p-6">
        <h2 className="text-lg font-semibold text-slate-900 dark:text-white mb-4">Threshold Configuration</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          <div>
            <label className="block text-sm font-medium text-slate-600 dark:text-slate-300 mb-1">
              Palm Distance Threshold: {thresholds.palm_distance_threshold.toFixed(3)}
            </label>
            <input
              type="range"
              min="0.05"
              max="0.30"
              step="0.005"
              title="Palm distance threshold"
              value={thresholds.palm_distance_threshold}
              onChange={e => setThresholds({ ...thresholds, palm_distance_threshold: parseFloat(e.target.value) })}
              className="w-full"
            />
            <div className="flex justify-between text-xs text-slate-400 dark:text-slate-500">
              <span>0.05</span><span>0.30</span>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-600 dark:text-slate-300 mb-1">
              Motion Threshold: {thresholds.motion_threshold.toFixed(3)}
            </label>
            <input
              type="range"
              min="0.005"
              max="0.05"
              step="0.001"
              title="Motion threshold"
              value={thresholds.motion_threshold}
              onChange={e => setThresholds({ ...thresholds, motion_threshold: parseFloat(e.target.value) })}
              className="w-full"
            />
            <div className="flex justify-between text-xs text-slate-400 dark:text-slate-500">
              <span>0.005</span><span>0.05</span>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-600 dark:text-slate-300 mb-1">
              Oscillation Threshold: {thresholds.oscillation_threshold}
            </label>
            <input
              type="range"
              min="1"
              max="10"
              step="1"
              title="Oscillation threshold"
              value={thresholds.oscillation_threshold}
              onChange={e => setThresholds({ ...thresholds, oscillation_threshold: parseInt(e.target.value) })}
              className="w-full"
            />
            <div className="flex justify-between text-xs text-slate-400 dark:text-slate-500">
              <span>1</span><span>10</span>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-600 dark:text-slate-300 mb-1">
              Score Threshold: {thresholds.score_threshold.toFixed(2)}
            </label>
            <input
              type="range"
              min="0.3"
              max="1.0"
              step="0.05"
              title="Score threshold"
              value={thresholds.score_threshold}
              onChange={e => setThresholds({ ...thresholds, score_threshold: parseFloat(e.target.value) })}
              className="w-full"
            />
            <div className="flex justify-between text-xs text-slate-400 dark:text-slate-500">
              <span>0.3</span><span>1.0</span>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-600 dark:text-slate-300 mb-1">
              Min Duration (sec): {thresholds.min_duration_sec.toFixed(1)}
            </label>
            <input
              type="range"
              min="0.5"
              max="10.0"
              step="0.5"
              title="Minimum duration"
              value={thresholds.min_duration_sec}
              onChange={e => setThresholds({ ...thresholds, min_duration_sec: parseFloat(e.target.value) })}
              className="w-full"
            />
            <div className="flex justify-between text-xs text-slate-400 dark:text-slate-500">
              <span>0.5s</span><span>10s</span>
            </div>
          </div>
        </div>

        {/* Apply to Profile */}
        <div className="mt-6 pt-4 border-t border-slate-200 dark:border-slate-700 flex gap-3 items-end flex-wrap">
          <div>
            <label className="block text-sm font-medium text-slate-600 dark:text-slate-300 mb-1">Profile Name</label>
            <input
              type="text"
              value={applyProfileName}
              onChange={e => setApplyProfileName(e.target.value)}
              className="border border-slate-300 dark:border-slate-600 dark:bg-slate-700 dark:text-white rounded-lg px-3 py-2 text-sm"
              placeholder="e.g. OR-1 Default"
            />
          </div>
          <button
            onClick={applyThresholds}
            disabled={loading || !selectedSessionId || !applyProfileName.trim()}
            className="bg-green-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-green-700 disabled:opacity-50"
          >
            Apply to Profile
          </button>
        </div>
      </div>

      {/* Sweep Results */}
      {sweepResults.length > 0 && (
        <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-card dark:shadow-none border border-slate-100 dark:border-slate-700 p-6">
          <h2 className="text-lg font-semibold text-slate-900 dark:text-white mb-4">
            Sweep Results (Top 10)
            {sweepBest && (
              <span className="ml-2 text-sm font-normal text-green-600">
                Best: {(sweepBest.accuracy * 100).toFixed(1)}% accuracy
              </span>
            )}
          </h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200 dark:border-slate-700 text-left text-slate-600 dark:text-slate-400">
                  <th className="pb-2 font-medium">#</th>
                  <th className="pb-2 font-medium">Palm Dist</th>
                  <th className="pb-2 font-medium">Motion</th>
                  <th className="pb-2 font-medium">Oscillation</th>
                  <th className="pb-2 font-medium">Score</th>
                  <th className="pb-2 font-medium">Accuracy</th>
                  <th className="pb-2 font-medium">Sensitivity</th>
                  <th className="pb-2 font-medium">Specificity</th>
                  <th className="pb-2 font-medium">TP/TN/FP/FN</th>
                  <th className="pb-2 font-medium">Action</th>
                </tr>
              </thead>
              <tbody>
                {sweepResults.map((r, i) => (
                  <tr key={i} className={`border-b border-slate-100 dark:border-slate-700 ${i === 0 ? 'bg-green-50 dark:bg-green-950/30' : ''}`}>
                    <td className="py-2 text-slate-500">{i + 1}</td>
                    <td className="py-2">{r.palm_distance_threshold}</td>
                    <td className="py-2">{r.motion_threshold}</td>
                    <td className="py-2">{r.oscillation_threshold}</td>
                    <td className="py-2">{r.score_threshold}</td>
                    <td className="py-2 font-medium">{(r.accuracy * 100).toFixed(1)}%</td>
                    <td className="py-2">{(r.sensitivity * 100).toFixed(1)}%</td>
                    <td className="py-2">{(r.specificity * 100).toFixed(1)}%</td>
                    <td className="py-2 text-slate-500">{r.tp}/{r.tn}/{r.fp}/{r.fn}</td>
                    <td className="py-2">
                      <button
                        onClick={() => setThresholds({
                          ...thresholds,
                          palm_distance_threshold: r.palm_distance_threshold,
                          motion_threshold: r.motion_threshold,
                          oscillation_threshold: r.oscillation_threshold,
                          score_threshold: r.score_threshold,
                        })}
                        className="text-brand-600 hover:text-brand-800 text-xs font-medium"
                      >
                        Use
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
