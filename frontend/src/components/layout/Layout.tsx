import { ReactNode, useState, useEffect, useRef } from 'react'
import { Link, useLocation } from 'react-router-dom'
import {
  Activity, BarChart3, Crosshair, LogOut, Users, Droplets,
  Calculator, SlidersHorizontal, Film, Camera, Menu, X,
  ChevronLeft, Shield, Moon, Sun,
} from 'lucide-react'
import { useAuthStore } from '../../stores/authStore'
import { useThemeStore } from '../../stores/themeStore'
import type { UserRole } from '../../types'

interface LayoutProps {
  children: ReactNode
}

const ROLE_ACCESS: Record<string, UserRole[]> = {
  '/':                     ['ADMIN', 'MANAGER', 'NURSE', 'SURGEON', 'TECHNICIAN', 'VIEWER'],
  '/analytics':            ['ADMIN', 'MANAGER', 'NURSE', 'SURGEON', 'TECHNICIAN', 'VIEWER'],
  '/calibration':          ['ADMIN', 'MANAGER'],
  '/gesture-calibration':  ['ADMIN', 'MANAGER'],
  '/staff':                ['ADMIN', 'MANAGER', 'NURSE', 'SURGEON'],
  '/dispensers':           ['ADMIN', 'MANAGER', 'NURSE', 'TECHNICIAN'],
  '/roi':                  ['ADMIN', 'MANAGER'],
  '/video':                ['ADMIN', 'MANAGER', 'TECHNICIAN'],
  '/camera':               ['ADMIN', 'MANAGER', 'TECHNICIAN'],
}

const NAV_SECTIONS = [
  {
    label: 'Overview',
    items: [
      { path: '/', label: 'Dashboard', icon: Activity },
      { path: '/analytics', label: 'Analytics', icon: BarChart3 },
    ],
  },
  {
    label: 'Monitoring',
    items: [
      { path: '/camera', label: 'Live Camera', icon: Camera },
      { path: '/video', label: 'Video Analysis', icon: Film },
    ],
  },
  {
    label: 'Configuration',
    items: [
      { path: '/calibration', label: 'Zone Calibration', icon: Crosshair },
      { path: '/gesture-calibration', label: 'Gesture Tuning', icon: SlidersHorizontal },
    ],
  },
  {
    label: 'Management',
    items: [
      { path: '/staff', label: 'Staff', icon: Users },
      { path: '/dispensers', label: 'Dispensers', icon: Droplets },
      { path: '/roi', label: 'ROI Calculator', icon: Calculator },
    ],
  },
]

export default function Layout({ children }: LayoutProps) {
  const location = useLocation()
  const { user, logout } = useAuthStore()
  const { theme, toggleTheme } = useThemeStore()
  const [collapsed, setCollapsed] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)

  // Safety net: sync HTML dark class with store state
  useEffect(() => {
    const root = document.documentElement
    if (theme === 'dark') {
      root.classList.add('dark')
    } else {
      root.classList.remove('dark')
    }
  }, [theme])

  // Page transition — re-trigger animation on route change
  const contentRef = useRef<HTMLDivElement>(null)
  const prevPath = useRef(location.pathname)

  useEffect(() => {
    if (prevPath.current !== location.pathname && contentRef.current) {
      prevPath.current = location.pathname
      const el = contentRef.current
      el.classList.remove('page-enter')
      // Force reflow to restart animation
      void el.offsetWidth
      el.classList.add('page-enter')
    }
  }, [location.pathname])

  const isAllowed = (path: string) => {
    if (!user) return false
    if (user.is_superuser) return true
    const allowed = ROLE_ACCESS[path]
    return !allowed || allowed.includes(user.role)
  }

  const closeMobile = () => setMobileOpen(false)
  const isDark = theme === 'dark'

  const sidebarContent = (
    <div className="flex flex-col h-full">
      {/* Logo */}
      <div className="flex items-center justify-between px-5 py-5 border-b border-slate-200 dark:border-white/[0.06]">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 bg-gradient-brand rounded-lg flex items-center justify-center flex-shrink-0 animate-glow-pulse">
            <Shield className="w-5 h-5 text-white" />
          </div>
          {!collapsed && (
            <div className="overflow-hidden">
              <h1 className="text-[15px] font-bold text-slate-900 dark:text-white tracking-tight leading-none">InfectionIQ</h1>
              <p className="text-[10px] text-slate-500 dark:text-slate-400 mt-0.5 uppercase tracking-widest">Infection Prevention</p>
            </div>
          )}
        </div>
      </div>

      {/* Nav sections */}
      <nav className="flex-1 overflow-y-auto py-4 px-3 space-y-5">
        {NAV_SECTIONS.map((section) => {
          const visibleItems = section.items.filter((i) => isAllowed(i.path))
          if (visibleItems.length === 0) return null
          return (
            <div key={section.label}>
              {!collapsed && (
                <p className="px-2 mb-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-400 dark:text-slate-500">
                  {section.label}
                </p>
              )}
              <div className="space-y-0.5">
                {visibleItems.map((item) => {
                  const active = location.pathname === item.path
                  return (
                    <Link
                      key={item.path}
                      to={item.path}
                      onClick={closeMobile}
                      className={`group flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-150 ${
                        active
                          ? 'bg-brand-50 dark:bg-brand-600/20 text-brand-700 dark:text-brand-300 shadow-sm'
                          : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-white/[0.05]'
                      }`}
                    >
                      <item.icon className={`w-[18px] h-[18px] flex-shrink-0 ${
                        active ? 'text-brand-600 dark:text-brand-400' : 'text-slate-400 dark:text-slate-500 group-hover:text-slate-600 dark:group-hover:text-slate-300'
                      }`} />
                      {!collapsed && <span>{item.label}</span>}
                    </Link>
                  )
                })}
              </div>
            </div>
          )
        })}
      </nav>

      {/* Theme toggle + Collapse */}
      <div className="border-t border-slate-200 dark:border-white/[0.06] px-3 py-2 space-y-1">
        {/* Theme toggle */}
        <button
          type="button"
          onClick={toggleTheme}
          className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-150 ${
            isDark
              ? 'text-amber-300 bg-amber-500/10 hover:bg-amber-500/20'
              : 'text-indigo-600 bg-indigo-50 hover:bg-indigo-100 dark:text-indigo-300 dark:bg-indigo-500/10'
          }`}
        >
          {isDark ? <Sun className="w-[18px] h-[18px]" /> : <Moon className="w-[18px] h-[18px]" />}
          {!collapsed && <span>{isDark ? 'Switch to Light' : 'Switch to Dark'}</span>}
        </button>

        {/* Collapse button (desktop only) */}
        <button
          type="button"
          onClick={() => setCollapsed(!collapsed)}
          className="hidden lg:flex w-full items-center justify-center gap-2 px-3 py-2 text-xs text-slate-400 dark:text-slate-500 hover:text-slate-600 dark:hover:text-slate-300 rounded-lg hover:bg-slate-100 dark:hover:bg-white/[0.04] transition-colors"
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          <ChevronLeft className={`w-4 h-4 transition-transform ${collapsed ? 'rotate-180' : ''}`} />
          {!collapsed && <span>Collapse</span>}
        </button>
      </div>

      {/* User */}
      {user && (
        <div className="border-t border-slate-200 dark:border-white/[0.06] px-4 py-4">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-brand-100 dark:bg-brand-700 flex items-center justify-center flex-shrink-0">
              <span className="text-xs font-bold text-brand-700 dark:text-brand-200">
                {(user.full_name || user.email || '?')[0].toUpperCase()}
              </span>
            </div>
            {!collapsed && (
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-slate-900 dark:text-slate-200 truncate">{user.full_name || user.email}</p>
                <p className="text-[11px] text-slate-500 truncate">{user.role}</p>
              </div>
            )}
            <button
              type="button"
              onClick={logout}
              className="p-1.5 text-slate-400 dark:text-slate-500 hover:text-red-500 dark:hover:text-red-400 hover:bg-red-50 dark:hover:bg-red-500/10 rounded-lg transition-colors flex-shrink-0"
              title="Sign out"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  )

  return (
    <div className="min-h-screen bg-[#f8fafc] dark:bg-[#0f172a] flex transition-colors duration-300">
      {/* Desktop sidebar */}
      <aside
        className={`hidden lg:flex flex-col fixed inset-y-0 left-0 z-30 bg-white dark:bg-sidebar shadow-lg dark:shadow-sidebar border-r border-slate-200 dark:border-transparent transition-all duration-200 ${
          collapsed ? 'w-[68px]' : 'w-60'
        }`}
      >
        {sidebarContent}
      </aside>

      {/* Mobile overlay */}
      {mobileOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={closeMobile} />
          <aside className="relative w-64 h-full bg-white dark:bg-sidebar shadow-sidebar animate-fade-in-up">
            {sidebarContent}
          </aside>
        </div>
      )}

      {/* Main area */}
      <div className={`flex-1 flex flex-col min-h-screen transition-all duration-200 ${
        collapsed ? 'lg:ml-[68px]' : 'lg:ml-60'
      }`}>
        {/* Mobile header */}
        <header className="lg:hidden bg-white dark:bg-slate-800 border-b border-slate-200 dark:border-slate-700 px-4 py-3 flex items-center justify-between sticky top-0 z-20 transition-colors">
          <button
            type="button"
            onClick={() => setMobileOpen(true)}
            className="p-2 text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg"
            aria-label="Open menu"
          >
            <Menu className="w-5 h-5" />
          </button>
          <div className="flex items-center gap-2">
            <Shield className="w-5 h-5 text-brand-600" />
            <span className="font-bold text-slate-900 dark:text-white text-sm">InfectionIQ</span>
          </div>
          {mobileOpen ? (
            <button
              type="button"
              onClick={closeMobile}
              className="p-2 text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg"
              aria-label="Close menu"
            >
              <X className="w-5 h-5" />
            </button>
          ) : (
            <div className="w-9" />
          )}
        </header>

        {/* Content with page transition */}
        <main className="flex-1 px-4 sm:px-6 lg:px-8 py-6 max-w-[1400px] w-full mx-auto">
          <div ref={contentRef} className="page-enter">
            {children}
          </div>
        </main>
      </div>
    </div>
  )
}
