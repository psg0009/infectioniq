export function getRiskBadgeColor(level: string): string {
  const colors: Record<string, string> = {
    LOW: 'text-green-600 bg-green-50',
    MODERATE: 'text-yellow-600 bg-yellow-50',
    HIGH: 'text-orange-600 bg-orange-50',
    CRITICAL: 'text-red-600 bg-red-50'
  }
  return colors[level] || 'text-slate-600 bg-slate-50'
}

export function getRiskBgColor(level: string): string {
  const colors: Record<string, string> = {
    LOW: 'bg-green-500',
    MODERATE: 'bg-yellow-500',
    HIGH: 'bg-orange-500',
    CRITICAL: 'bg-red-500'
  }
  return colors[level] || 'bg-slate-500'
}
