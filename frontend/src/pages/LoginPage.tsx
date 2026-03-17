import { useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { LogIn, UserPlus, Shield, Eye, EyeOff, Camera, Hand, ShieldCheck, Bell, ArrowRight, Moon, Sun } from 'lucide-react'
import { useAuthStore } from '../stores/authStore'
import { useThemeStore } from '../stores/themeStore'

const STEPS = [
  { icon: Camera, label: 'Capture', color: '#09c4ae' },
  { icon: Hand, label: 'Detect', color: '#3b82f6' },
  { icon: ShieldCheck, label: 'Evaluate', color: '#10b981' },
  { icon: Bell, label: 'Alert', color: '#f59e0b' },
]

export default function LoginPage() {
  const [isRegister, setIsRegister] = useState(false)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [fullName, setFullName] = useState('')
  const [error, setError] = useState('')
  const [showPassword, setShowPassword] = useState(false)

  const { login, register, loginWithGoogle, isLoading } = useAuthStore()
  const { theme, toggleTheme } = useThemeStore()
  const navigate = useNavigate()
  const location = useLocation()
  const from = (location.state as { from?: string })?.from || '/'
  const isDark = theme === 'dark'

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    try {
      if (isRegister) {
        await register(email, password, fullName)
      } else {
        await login(email, password)
      }
      navigate(from, { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Authentication failed')
    }
  }

  const handleGoogle = async () => {
    setError('')
    try {
      await loginWithGoogle()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Google sign-in failed')
    }
  }

  return (
    <div className="min-h-screen relative overflow-hidden flex flex-col bg-[#f0f4f8] dark:bg-[#060b18] transition-colors duration-500">
      {/* Background gradient overlay (dark mode only) */}
      <div
        className="absolute inset-0 opacity-0 dark:opacity-100 transition-opacity duration-500"
        style={{
          background: 'linear-gradient(145deg, #060b18 0%, #0a1628 25%, #0b2230 55%, #082b2e 85%, #0a1e20 100%)',
        }}
      />

      {/* Light mode subtle gradient */}
      <div
        className="absolute inset-0 opacity-100 dark:opacity-0 transition-opacity duration-500"
        style={{
          background: 'linear-gradient(145deg, #f0f4f8 0%, #e8f0f5 30%, #e0f2f1 60%, #e6f7f5 100%)',
        }}
      />

      {/* Animated orbs */}
      <div className="absolute w-[600px] h-[600px] rounded-full opacity-10 dark:opacity-20 blur-[120px] animate-float"
        style={{ background: 'radial-gradient(circle, #09c4ae, transparent 70%)', top: '-10%', left: '5%' }}
      />
      <div className="absolute w-[700px] h-[700px] rounded-full opacity-[0.06] dark:opacity-[0.12] blur-[140px] animate-float-delayed"
        style={{ background: 'radial-gradient(circle, #20e0c7, transparent 70%)', bottom: '-15%', right: '-8%' }}
      />
      <div className="absolute w-[400px] h-[400px] rounded-full opacity-[0.04] dark:opacity-[0.06] blur-[100px] animate-float-slow"
        style={{ background: 'radial-gradient(circle, #53f5db, transparent 70%)', top: '35%', left: '45%' }}
      />

      {/* Dot grid */}
      <div className="absolute inset-0 opacity-[0.02] dark:opacity-[0.035]" style={{
        backgroundImage: 'radial-gradient(circle at 1px 1px, rgba(9,196,174,0.6) 1px, transparent 0)',
        backgroundSize: '40px 40px',
      }} />

      {/* Top bar */}
      <header className="relative z-20 flex items-center justify-between px-10 pt-8 animate-fade-in-up">
        <div className="flex items-center gap-3">
          <div className="w-11 h-11 bg-gradient-brand rounded-xl flex items-center justify-center animate-glow-pulse">
            <Shield className="w-6 h-6 text-white" />
          </div>
          <span className="text-xl font-bold text-slate-900 dark:text-white tracking-tight transition-colors">InfectionIQ</span>
        </div>
        {/* Theme toggle */}
        <button
          type="button"
          onClick={toggleTheme}
          title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
          className="w-10 h-10 rounded-xl flex items-center justify-center text-slate-500 dark:text-slate-400 hover:text-brand-600 dark:hover:text-brand-300 bg-white/60 dark:bg-white/[0.06] border border-slate-200 dark:border-white/[0.08] hover:border-brand-300 dark:hover:border-brand-500/30 backdrop-blur-sm transition-all duration-200 hover:scale-105"
        >
          {isDark ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
        </button>
      </header>

      {/* Main — vertically centered */}
      <div className="relative z-10 flex-1 flex items-center">
        <div className="w-full max-w-7xl mx-auto px-10 py-12 flex flex-col lg:flex-row lg:items-center lg:gap-24">

          {/* Left — hero */}
          <div className="flex-1 max-w-2xl animate-fade-in-up">
            <h1 className="text-5xl sm:text-6xl lg:text-7xl font-extrabold leading-[1.05] tracking-tight">
              <span className="text-slate-900 dark:text-white transition-colors">AI-Powered</span><br />
              <span className="bg-gradient-to-r from-brand-600 via-brand-500 to-brand-400 dark:from-brand-300 dark:via-brand-400 dark:to-brand-200 bg-clip-text text-transparent">
                Infection Prevention
              </span>
            </h1>
            <p className="text-slate-600 dark:text-slate-400 mt-6 max-w-lg leading-relaxed text-lg transition-colors">
              Computer vision that monitors hand hygiene compliance in real-time — so your team can focus on patient care.
            </p>

            {/* How it works — horizontal step flow */}
            <div className="mt-14">
              <div className="flex items-center">
                {STEPS.map((s, i) => (
                  <div key={i} className="flex items-center">
                    <div className="group flex flex-col items-center gap-3 w-24">
                      <div
                        className="w-16 h-16 rounded-2xl flex items-center justify-center group-hover:scale-110 transition-transform duration-300"
                        style={{
                          background: `linear-gradient(135deg, ${s.color}15, ${s.color}30)`,
                          boxShadow: `0 0 30px ${s.color}12`,
                          border: `1px solid ${s.color}28`,
                        }}
                      >
                        <s.icon className="w-7 h-7" style={{ color: s.color }} />
                      </div>
                      <span className="text-sm font-semibold text-slate-500 dark:text-slate-400 group-hover:text-slate-900 dark:group-hover:text-white transition-colors">{s.label}</span>
                    </div>
                    {i < 3 && (
                      <ArrowRight className="w-5 h-5 text-slate-300 dark:text-slate-600 mb-7 mx-1 flex-shrink-0 transition-colors" />
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* Trust badges */}
            <div className="mt-12 flex items-center gap-10">
              {[
                { val: '99.2%', label: 'Accuracy' },
                { val: '<50ms', label: 'Latency' },
                { val: '24/7', label: 'Monitoring' },
              ].map((b, i) => (
                <div key={i}>
                  <p className="text-2xl font-bold text-brand-600 dark:text-brand-400 transition-colors">{b.val}</p>
                  <p className="text-xs text-slate-400 dark:text-slate-500 uppercase tracking-wider mt-0.5 transition-colors">{b.label}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Right — login card */}
          <div className="w-full lg:w-[440px] flex-shrink-0 mt-14 lg:mt-0 animate-fade-in-up-delay-1">
            <div className="rounded-3xl p-8 backdrop-blur-xl bg-white/80 dark:bg-white/[0.06] border border-slate-200 dark:border-white/[0.1] shadow-xl dark:shadow-[0_12px_48px_rgba(0,0,0,0.4)] transition-all duration-300">
              <h2 className="text-2xl font-bold text-slate-900 dark:text-white mb-1 transition-colors">
                {isRegister ? 'Create account' : 'Welcome back'}
              </h2>
              <p className="text-sm text-slate-500 dark:text-slate-400 mb-7 transition-colors">
                {isRegister ? 'Get started with InfectionIQ' : 'Sign in to your dashboard'}
              </p>

              {/* Google OAuth */}
              <button
                type="button"
                onClick={handleGoogle}
                disabled={isLoading}
                className="w-full flex items-center justify-center gap-3 px-4 py-3 rounded-xl text-sm font-medium text-slate-700 dark:text-white/90 bg-white dark:bg-white/[0.04] border border-slate-200 dark:border-white/[0.1] hover:bg-slate-50 dark:hover:bg-white/[0.08] hover:border-slate-300 dark:hover:border-white/[0.15] disabled:opacity-50 transition-all duration-200"
              >
                <svg className="w-5 h-5" viewBox="0 0 24 24">
                  <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"/>
                  <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                  <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                  <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
                </svg>
                Continue with Google
              </button>

              {/* Divider */}
              <div className="flex items-center gap-3 my-6">
                <div className="flex-1 h-px bg-slate-200 dark:bg-white/[0.08]" />
                <span className="text-[11px] text-slate-400 dark:text-slate-500 uppercase tracking-widest font-medium">or</span>
                <div className="flex-1 h-px bg-slate-200 dark:bg-white/[0.08]" />
              </div>

              {error && (
                <div className="bg-red-50 dark:bg-red-500/10 text-red-600 dark:text-red-400 px-4 py-3 rounded-xl mb-4 text-sm border border-red-200 dark:border-red-500/20 flex items-center gap-2">
                  <div className="w-1.5 h-1.5 bg-red-500 rounded-full flex-shrink-0" />
                  {error}
                </div>
              )}

              <form onSubmit={handleSubmit} className="space-y-4">
                {isRegister && (
                  <div>
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-400 mb-1.5 transition-colors">Full Name</label>
                    <input
                      type="text"
                      value={fullName}
                      onChange={(e) => setFullName(e.target.value)}
                      placeholder="Dr. Jane Smith"
                      className="w-full px-4 py-3 bg-slate-50 dark:bg-white/[0.05] border border-slate-200 dark:border-white/[0.08] rounded-xl text-sm text-slate-900 dark:text-white placeholder-slate-400 dark:placeholder-slate-500 focus:ring-2 focus:ring-brand-500/20 dark:focus:ring-brand-500/30 focus:border-brand-500 dark:focus:border-brand-500/50 outline-none transition-all duration-200"
                      required
                    />
                  </div>
                )}

                <div>
                  <label className="block text-sm font-medium text-slate-700 dark:text-slate-400 mb-1.5 transition-colors">Email</label>
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="you@hospital.org"
                    className="w-full px-4 py-3 bg-slate-50 dark:bg-white/[0.05] border border-slate-200 dark:border-white/[0.08] rounded-xl text-sm text-slate-900 dark:text-white placeholder-slate-400 dark:placeholder-slate-500 focus:ring-2 focus:ring-brand-500/20 dark:focus:ring-brand-500/30 focus:border-brand-500 dark:focus:border-brand-500/50 outline-none transition-all duration-200"
                    required
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-700 dark:text-slate-400 mb-1.5 transition-colors">Password</label>
                  <div className="relative">
                    <input
                      type={showPassword ? 'text' : 'password'}
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="Min. 8 characters"
                      className="w-full px-4 py-3 bg-slate-50 dark:bg-white/[0.05] border border-slate-200 dark:border-white/[0.08] rounded-xl text-sm text-slate-900 dark:text-white placeholder-slate-400 dark:placeholder-slate-500 focus:ring-2 focus:ring-brand-500/20 dark:focus:ring-brand-500/30 focus:border-brand-500 dark:focus:border-brand-500/50 outline-none transition-all duration-200 pr-11"
                      required
                      minLength={6}
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute right-3.5 top-1/2 -translate-y-1/2 text-slate-400 dark:text-slate-500 hover:text-slate-600 dark:hover:text-slate-300 transition-colors"
                      title={showPassword ? 'Hide password' : 'Show password'}
                      tabIndex={-1}
                    >
                      {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={isLoading}
                  className="w-full py-3 rounded-xl font-semibold text-sm text-white disabled:opacity-50 flex items-center justify-center gap-2 transition-all duration-200 hover:scale-[1.01] active:scale-[0.99] mt-2 bg-gradient-brand shadow-glow-brand hover:opacity-90"
                >
                  {isLoading ? (
                    <>
                      <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                      Please wait...
                    </>
                  ) : isRegister ? (
                    <><UserPlus className="w-4 h-4" /> Create Account</>
                  ) : (
                    <><LogIn className="w-4 h-4" /> Sign In</>
                  )}
                </button>
              </form>

              <p className="text-center text-sm text-slate-500 dark:text-slate-500 mt-6">
                {isRegister ? 'Already have an account?' : "Don't have an account?"}{' '}
                <button
                  type="button"
                  onClick={() => { setIsRegister(!isRegister); setError('') }}
                  className="text-brand-600 dark:text-brand-400 font-semibold hover:text-brand-700 dark:hover:text-brand-300 transition-colors"
                >
                  {isRegister ? 'Sign In' : 'Create Account'}
                </button>
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
