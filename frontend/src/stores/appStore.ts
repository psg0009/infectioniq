import { create } from 'zustand'
import type { SurgicalCase, Alert, DashboardMetrics, DispenserStatus } from '../types'

interface AppState {
  // Data
  activeCases: SurgicalCase[]
  alerts: Alert[]
  metrics: DashboardMetrics | null
  dispensers: DispenserStatus[]
  
  // WebSocket
  wsConnected: boolean
  
  // Actions
  setActiveCases: (cases: SurgicalCase[]) => void
  setAlerts: (alerts: Alert[]) => void
  addAlert: (alert: Alert) => void
  acknowledgeAlert: (id: string) => void
  setMetrics: (metrics: DashboardMetrics) => void
  setDispensers: (dispensers: DispenserStatus[]) => void
  setWsConnected: (connected: boolean) => void
}

export const useAppStore = create<AppState>((set) => ({
  activeCases: [],
  alerts: [],
  metrics: null,
  dispensers: [],
  wsConnected: false,

  setActiveCases: (cases) => set({ activeCases: cases }),

  setAlerts: (alerts) => set({ alerts }),

  addAlert: (alert) => set((state) => ({
    alerts: [alert, ...state.alerts].slice(0, 50)
  })),
  
  acknowledgeAlert: (id) => set((state) => ({
    alerts: state.alerts.map(a => 
      a.id === id ? { ...a, acknowledged: true } : a
    )
  })),
  
  setMetrics: (metrics) => set({ metrics }),
  setDispensers: (dispensers) => set({ dispensers }),
  setWsConnected: (connected) => set({ wsConnected: connected }),
}))
