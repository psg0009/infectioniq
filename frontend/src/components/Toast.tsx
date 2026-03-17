import { useEffect } from 'react'
import { X, CheckCircle, AlertTriangle, Info, XCircle } from 'lucide-react'
import { create } from 'zustand'

interface ToastMessage {
  id: string
  type: 'success' | 'error' | 'warning' | 'info'
  message: string
  duration?: number
}

interface ToastState {
  toasts: ToastMessage[]
  addToast: (toast: Omit<ToastMessage, 'id'>) => void
  removeToast: (id: string) => void
}

export const useToastStore = create<ToastState>((set) => ({
  toasts: [],
  addToast: (toast) =>
    set((state) => ({
      toasts: [...state.toasts, { ...toast, id: Date.now().toString() }],
    })),
  removeToast: (id) =>
    set((state) => ({
      toasts: state.toasts.filter((t) => t.id !== id),
    })),
}))

export function toast(type: ToastMessage['type'], message: string, duration = 5000) {
  useToastStore.getState().addToast({ type, message, duration })
}

const icons = {
  success: <CheckCircle className="w-5 h-5 text-green-500" />,
  error: <XCircle className="w-5 h-5 text-red-500" />,
  warning: <AlertTriangle className="w-5 h-5 text-amber-500" />,
  info: <Info className="w-5 h-5 text-blue-500" />,
}

const bgColors = {
  success: 'bg-green-50 border-green-100 dark:bg-green-950/50 dark:border-green-900',
  error: 'bg-red-50 border-red-100 dark:bg-red-950/50 dark:border-red-900',
  warning: 'bg-amber-50 border-amber-100 dark:bg-amber-950/50 dark:border-amber-900',
  info: 'bg-blue-50 border-blue-100 dark:bg-blue-950/50 dark:border-blue-900',
}

function ToastItem({ toast: t, onClose }: { toast: ToastMessage; onClose: () => void }) {
  useEffect(() => {
    const timer = setTimeout(onClose, t.duration || 5000)
    return () => clearTimeout(timer)
  }, [t.duration, onClose])

  return (
    <div className={`flex items-center gap-3 px-4 py-3 rounded-xl border shadow-card-hover ${bgColors[t.type]}`}>
      {icons[t.type]}
      <p className="text-sm text-slate-800 dark:text-slate-200 flex-1">{t.message}</p>
      <button type="button" title="Dismiss" onClick={onClose} className="text-slate-400 hover:text-slate-300 dark:hover:text-slate-100">
        <X className="w-4 h-4" />
      </button>
    </div>
  )
}

export default function ToastContainer() {
  const { toasts, removeToast } = useToastStore()

  return (
    <div className="fixed top-4 right-4 z-50 space-y-2 max-w-sm">
      {toasts.map((t) => (
        <ToastItem key={t.id} toast={t} onClose={() => removeToast(t.id)} />
      ))}
    </div>
  )
}
