import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'

export default function SSOCallbackPage() {
  const navigate = useNavigate()
  const initSession = useAuthStore((s) => s.initSession)

  useEffect(() => {
    // Supabase OAuth redirect sets the session via URL hash automatically.
    // initSession() picks it up from supabase.auth.getSession().
    initSession().then(() => {
      navigate('/', { replace: true })
    })
  }, [navigate, initSession])

  return (
    <div className="min-h-screen bg-slate-100 flex items-center justify-center">
      <p className="text-slate-500">Completing sign-in...</p>
    </div>
  )
}
