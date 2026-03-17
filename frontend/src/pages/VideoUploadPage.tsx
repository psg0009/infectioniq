import { useState, useEffect, useCallback } from 'react'
import { Upload, Play, Trash2, CheckCircle, XCircle, Loader2, Film } from 'lucide-react'
import { API_URL } from '../config'
import { authHeaders } from '../utils/api'

interface VideoJob {
  job_id: string
  status: 'QUEUED' | 'PROCESSING' | 'COMPLETED' | 'FAILED'
  filename: string
  case_id?: string
  or_number: string
  started_at?: string
  completed_at?: string
  error?: string
}

export default function VideoUploadPage() {
  const [file, setFile] = useState<File | null>(null)
  const [orNumber, setOrNumber] = useState('OR-1')
  const [caseId, setCaseId] = useState('')
  const [sampleFrames, setSampleFrames] = useState(false)
  const [demoMode, setDemoMode] = useState(false)
  const [demoCompliant, setDemoCompliant] = useState(5)
  const [demoNonCompliant, setDemoNonCompliant] = useState(3)
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState('')
  const [jobs, setJobs] = useState<VideoJob[]>([])
  const [dragOver, setDragOver] = useState(false)

  const fetchJobs = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/v1/video/jobs`, {
        headers: authHeaders(),
      })
      if (res.ok) {
        const data = await res.json()
        setJobs(data.jobs || [])
      }
    } catch {
      // ignore
    }
  }, [])

  // Poll for job updates
  useEffect(() => {
    fetchJobs()
    const interval = setInterval(fetchJobs, 3000)
    return () => clearInterval(interval)
  }, [fetchJobs])

  const handleUpload = async () => {
    if (!file) return
    setUploading(true)
    setUploadError('')

    try {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('or_number', orNumber)
      if (caseId) formData.append('case_id', caseId)
      formData.append('sample_frames', String(sampleFrames))
      formData.append('demo_mode', String(demoMode))
      if (demoMode) {
        formData.append('demo_compliant', String(demoCompliant))
        formData.append('demo_non_compliant', String(demoNonCompliant))
      }

      const res = await fetch(`${API_URL}/api/v1/video/upload`, {
        method: 'POST',
        headers: authHeaders(),
        body: formData,
      })

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Upload failed' }))
        throw new Error(err.detail || `Upload failed (${res.status})`)
      }

      setFile(null)
      setCaseId('')
      fetchJobs()
    } catch (e: any) {
      setUploadError(e.message)
    } finally {
      setUploading(false)
    }
  }

  const handleDelete = async (jobId: string) => {
    try {
      await fetch(`${API_URL}/api/v1/video/jobs/${jobId}`, {
        method: 'DELETE',
        headers: authHeaders(),
      })
      fetchJobs()
    } catch {
      // ignore
    }
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    const dropped = e.dataTransfer.files[0]
    if (dropped && dropped.type.startsWith('video/')) {
      setFile(dropped)
    }
  }

  const statusBadge = (status: string) => {
    switch (status) {
      case 'QUEUED':
        return <span className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium rounded-full bg-slate-100 text-slate-600"><Loader2 className="w-3 h-3 animate-spin" /> Queued</span>
      case 'PROCESSING':
        return <span className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium rounded-full bg-blue-100 text-blue-700"><Loader2 className="w-3 h-3 animate-spin" /> Processing</span>
      case 'COMPLETED':
        return <span className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium rounded-full bg-green-100 text-green-700"><CheckCircle className="w-3 h-3" /> Completed</span>
      case 'FAILED':
        return <span className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium rounded-full bg-red-100 text-red-700"><XCircle className="w-3 h-3" /> Failed</span>
      default:
        return <span className="px-2 py-1 text-xs rounded-full bg-slate-100">{status}</span>
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Video Analysis</h1>
        <p className="text-slate-500 dark:text-slate-400 mt-1">Upload OR footage to run the CV pipeline and generate compliance events</p>
      </div>

      {/* Upload Card */}
      <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-card dark:shadow-none border border-slate-100 dark:border-slate-700 p-6">
        <h2 className="text-lg font-semibold text-slate-900 dark:text-white mb-4">Upload Video</h2>

        {/* Drop Zone */}
        <div
          onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          onClick={() => document.getElementById('video-input')?.click()}
          className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors ${
            dragOver
              ? 'border-blue-400 bg-blue-50'
              : file
              ? 'border-green-300 bg-green-50'
              : 'border-slate-300 hover:border-blue-400 hover:bg-slate-50'
          }`}
        >
          <input
            id="video-input"
            type="file"
            accept="video/*"
            title="Select video file"
            className="hidden"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
          />
          {file ? (
            <div className="flex flex-col items-center gap-2">
              <Film className="w-10 h-10 text-green-500" />
              <p className="font-medium text-slate-900">{file.name}</p>
              <p className="text-sm text-slate-500">{(file.size / 1024 / 1024).toFixed(1)} MB</p>
            </div>
          ) : (
            <div className="flex flex-col items-center gap-2">
              <Upload className="w-10 h-10 text-slate-400" />
              <p className="font-medium text-slate-700">Drop a video file here or click to browse</p>
              <p className="text-sm text-slate-400">MP4, AVI, MOV, MKV, WebM — up to 500 MB</p>
            </div>
          )}
        </div>

        {/* Options */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mt-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">OR Number</label>
            <select
              value={orNumber}
              onChange={(e) => setOrNumber(e.target.value)}
              title="Select OR number"
              className="w-full border border-slate-300 dark:border-slate-600 dark:bg-slate-700 dark:text-white rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500"
            >
              {['OR-1', 'OR-2', 'OR-3', 'OR-4', 'OR-5', 'OR-6', 'OR-7', 'OR-8'].map(or => (
                <option key={or} value={or}>{or}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">Case ID (optional)</label>
            <input
              type="text"
              value={caseId}
              onChange={(e) => setCaseId(e.target.value)}
              placeholder="Link to existing case"
              className="w-full border border-slate-300 dark:border-slate-600 dark:bg-slate-700 dark:text-white rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500"
            />
          </div>
          <div className="flex flex-col justify-end gap-2">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={demoMode}
                onChange={(e) => setDemoMode(e.target.checked)}
                className="w-4 h-4 text-blue-600 rounded border-slate-300"
              />
              <span className="text-sm text-slate-700">Demo Mode</span>
            </label>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={sampleFrames}
                onChange={(e) => setSampleFrames(e.target.checked)}
                className="w-4 h-4 text-blue-600 rounded border-slate-300"
              />
              <span className="text-sm text-slate-700">Collect training frames</span>
            </label>
          </div>
        </div>

        {demoMode && (
          <div className="mt-4 p-4 bg-blue-50 border border-blue-200 rounded-lg space-y-3">
            <p className="text-sm text-blue-700">
              <strong>Demo Mode:</strong> Simulates staff entering the OR with configurable compliance.
              Events appear on the dashboard in real-time. Upload any video to trigger.
            </p>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-green-700 mb-1">Compliant (sanitize)</label>
                <input
                  type="number"
                  min={0}
                  max={20}
                  value={demoCompliant}
                  onChange={(e) => setDemoCompliant(Math.max(0, Math.min(20, Number(e.target.value))))}
                  title="Number of compliant staff"
                  className="w-full border border-green-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-green-500 focus:border-green-500 bg-white"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-red-700 mb-1">Non-compliant (skip)</label>
                <input
                  type="number"
                  min={0}
                  max={20}
                  value={demoNonCompliant}
                  onChange={(e) => setDemoNonCompliant(Math.max(0, Math.min(20, Number(e.target.value))))}
                  title="Number of non-compliant staff"
                  className="w-full border border-red-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-red-500 focus:border-red-500 bg-white"
                />
              </div>
            </div>
            <p className="text-xs text-blue-600">
              Total: {demoCompliant + demoNonCompliant} staff &middot; Expected compliance: {demoCompliant + demoNonCompliant > 0 ? ((demoCompliant / (demoCompliant + demoNonCompliant)) * 100).toFixed(0) : 0}%
            </p>
          </div>
        )}

        {uploadError && (
          <div className="mt-3 p-3 bg-red-50 text-red-700 text-sm rounded-lg">{uploadError}</div>
        )}

        <button
          onClick={handleUpload}
          disabled={!file || uploading}
          className="mt-4 w-full sm:w-auto inline-flex items-center justify-center gap-2 px-6 py-2.5 bg-gradient-brand text-white font-semibold rounded-xl hover:opacity-90 shadow-glow-brand disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {uploading ? (
            <><Loader2 className="w-4 h-4 animate-spin" /> Uploading...</>
          ) : (
            <><Play className="w-4 h-4" /> Upload & Analyze</>
          )}
        </button>
      </div>

      {/* Jobs List */}
      {jobs.length > 0 && (
        <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-card dark:shadow-none border border-slate-100 dark:border-slate-700 p-6">
          <h2 className="text-lg font-semibold text-slate-900 dark:text-white mb-4">Processing Jobs</h2>
          <div className="space-y-3">
            {jobs.map((job) => (
              <div
                key={job.job_id}
                className="flex items-center justify-between p-4 bg-slate-50 dark:bg-slate-700/50 rounded-lg"
              >
                <div className="flex items-center gap-4">
                  <Film className="w-5 h-5 text-slate-400" />
                  <div>
                    <p className="font-medium text-slate-900 dark:text-white">{job.filename}</p>
                    <p className="text-xs text-slate-500">
                      {job.or_number}
                      {job.case_id && ` · Case: ${job.case_id.slice(0, 8)}...`}
                      {job.started_at && ` · Started: ${new Date(job.started_at).toLocaleTimeString()}`}
                      {job.completed_at && ` · Done: ${new Date(job.completed_at).toLocaleTimeString()}`}
                    </p>
                    {job.error && (
                      <p className="text-xs text-red-600 mt-1">{job.error.slice(0, 200)}</p>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  {statusBadge(job.status)}
                  <button
                    onClick={() => handleDelete(job.job_id)}
                    className="p-1.5 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                    title="Delete job"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
