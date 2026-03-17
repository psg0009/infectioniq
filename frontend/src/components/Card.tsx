import { ReactNode } from 'react'

interface CardProps {
  children: React.ReactNode
  className?: string
  hover?: boolean
}

export default function Card({ children, className = '', hover = false }: CardProps) {
  return (
    <div className={`bg-white dark:bg-slate-800 rounded-2xl shadow-card dark:shadow-none border border-slate-100 dark:border-slate-700 p-6 transition-colors ${
      hover ? 'hover:shadow-card-hover dark:hover:border-slate-600 hover:border-slate-200 transition-all duration-200' : ''
    } ${className}`}>
      {children}
    </div>
  )
}

export function CardHeader({ title, subtitle, action }: {
  title: string
  subtitle?: string
  action?: ReactNode
}) {
  return (
    <div className="flex items-center justify-between mb-5">
      <div>
        <h2 className="text-base font-semibold text-slate-900 dark:text-white">{title}</h2>
        {subtitle && <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">{subtitle}</p>}
      </div>
      {action}
    </div>
  )
}
