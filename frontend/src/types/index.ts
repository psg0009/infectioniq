// Types for InfectionIQ Frontend

export type UserRole = 'ADMIN' | 'MANAGER' | 'NURSE' | 'SURGEON' | 'TECHNICIAN' | 'VIEWER'

export type SubscriptionTier = 'TRIAL' | 'STARTER' | 'PROFESSIONAL' | 'ENTERPRISE'

export interface User {
  id: string
  email: string
  full_name: string
  role: UserRole
  subscription_tier: SubscriptionTier
  max_ors: number
  is_active: boolean
  is_superuser: boolean
  staff_id?: string
  last_login?: string
  created_at: string
}

export type RiskLevel = 'LOW' | 'MODERATE' | 'HIGH' | 'CRITICAL'
export type PersonState = 'UNKNOWN' | 'CLEAN' | 'POTENTIALLY_CONTAMINATED' | 'CONTAMINATED' | 'DIRTY'
export type AlertSeverity = 'INFO' | 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
export type Zone = 'CRITICAL' | 'STERILE' | 'NON_STERILE' | 'SANITIZER' | 'DOOR'
export type CaseStatus = 'SCHEDULED' | 'IN_PROGRESS' | 'COMPLETED' | 'CANCELLED'

export interface Staff {
  id: string
  employee_id: string
  name: string
  role: string
  department?: string
}

export interface RiskScore {
  score: number
  risk_level: RiskLevel
  factors: RiskFactor[]
  recommendations: string[]
}

export interface RiskFactor {
  name: string
  value: number
  weight: number
  description: string
}

export interface SurgicalCase {
  id: string
  or_number: string
  procedure_type: string
  start_time: string
  end_time?: string
  status: CaseStatus
  surgeon_id?: string
  risk_score?: RiskScore
}

export interface Alert {
  id: string
  case_id: string
  alert_type: string
  severity: AlertSeverity
  message: string
  timestamp: string
  acknowledged: boolean
}

export interface TouchEvent {
  id: string
  case_id: string
  timestamp: string
  zone: Zone
  surface?: string
  person_state_before: PersonState
  person_state_after: PersonState
}

export interface ComplianceMetrics {
  overall_rate: number
  total_entries: number
  compliant_entries: number
  violations: number
}

export interface DashboardMetrics {
  active_cases: number
  overall_compliance_rate: number
  active_alerts: number
  critical_alerts: number
  dispensers_low: number
  today_entries: number
  today_violations: number
}

export interface DispenserStatus {
  dispenser_id: string
  or_number: string
  level_percent: number
  status: string
  days_until_expiration?: number
}
