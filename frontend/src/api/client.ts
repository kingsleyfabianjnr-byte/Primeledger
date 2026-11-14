/**
 * Typed API client — all backend calls go through this module.
 * In development: Vite proxies /api → localhost:8000
 * In production:  VITE_API_URL points to the IBM Code Engine backend URL
 */
import axios from 'axios'

const BASE = import.meta.env.VITE_API_URL
  ? `${import.meta.env.VITE_API_URL}/api`
  : '/api'

const api = axios.create({
  baseURL: BASE,
  headers: { 'Content-Type': 'application/json' },
})

// Attach JWT token automatically
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('pl_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Auto-logout on 401
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('pl_token')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

export default api

// ── Types ─────────────────────────────────────────────────────────────────────

export type UserRole = 'admin' | 'preparer' | 'approver' | 'viewer'

export interface User {
  id: number
  email: string
  full_name: string
  role: UserRole
  is_active: boolean
  created_at: string
  last_login: string | null
}

export interface BankAccount {
  id: number
  name: string
  account_number: string
  masked_number: string
  entity_name: string
  currency: string
  is_active: boolean
  created_at: string
}

export type ReconciliationStatus =
  | 'pending'
  | 'in_progress'
  | 'awaiting_approval'
  | 'approved'
  | 'rejected'

export interface Reconciliation {
  id: number
  bank_account_id: number
  period_start: string
  period_end: string
  status: ReconciliationStatus
  total_transactions: number
  matched_count: number
  exception_count: number
  bank_balance: string | null
  ledger_balance: string | null
  created_at: string
  completed_at: string | null
  bank_account?: BankAccount
}

export type ExceptionStatus = 'open' | 'pending_approval' | 'approved' | 'rejected'

export interface Exception {
  id: number
  reconciliation_id: number
  bank_transaction_id: number | null
  exception_number: number
  exception_type: string
  description: string
  ai_explanation: string
  confidence_score: string
  suggested_debit: string | null
  suggested_credit: string | null
  suggested_amount: string | null
  status: ExceptionStatus
  reviewed_by_id: number | null
  reviewed_at: string | null
  reviewer_note: string | null
  created_at: string
}

export type AuditAction =
  | 'match_created'
  | 'exception_raised'
  | 'entry_approved'
  | 'entry_rejected'
  | 'entry_edited'
  | 'reconciliation_started'
  | 'reconciliation_completed'
  | 'user_logged_in'

export interface AuditLog {
  id: number
  reconciliation_id: number | null
  user_id: number | null
  action: AuditAction
  entity_type: string
  entity_id: number | null
  details: Record<string, unknown> | null
  previous_hash: string | null
  entry_hash: string
  created_at: string
}

export interface DashboardStats {
  total_accounts: number
  active_reconciliations: number
  exceptions_open: number
  matches_this_month: number
  match_rate: number
  reconciliations: Reconciliation[]
}

// ── API calls ─────────────────────────────────────────────────────────────────

export const authApi = {
  login: (email: string, password: string) =>
    api.post<{ access_token: string; token_type: string }>(
      '/auth/token',
      new URLSearchParams({ username: email, password }),
      { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } }
    ),
  me: () => api.get<User>('/auth/me'),
  register: (data: { email: string; full_name: string; password: string; role?: string }) =>
    api.post<User>('/auth/register', data),
}

export const dashboardApi = {
  get: () => api.get<DashboardStats>('/dashboard'),
}

export const exceptionsApi = {
  list: (params?: { reconciliation_id?: number; status?: ExceptionStatus }) =>
    api.get<Exception[]>('/exceptions', { params }),
  get: (id: number) => api.get<Exception>(`/exceptions/${id}`),
  review: (
    id: number,
    payload: {
      action: 'approve' | 'reject' | 'edit'
      reviewer_note?: string
      suggested_debit?: string
      suggested_credit?: string
      suggested_amount?: string
    }
  ) => api.post<Exception>(`/exceptions/${id}/review`, payload),
}

export const reconciliationsApi = {
  list: (params?: { account_id?: number; status?: ReconciliationStatus }) =>
    api.get<Reconciliation[]>('/reconciliations', { params }),
  get: (id: number) => api.get<Reconciliation>(`/reconciliations/${id}`),
  create: (data: { bank_account_id: number; period_start: string; period_end: string }) =>
    api.post<Reconciliation>('/reconciliations', data),
}

export const auditApi = {
  list: (params?: { reconciliation_id?: number; limit?: number; offset?: number }) =>
    api.get<AuditLog[]>('/audit', { params }),
  get: (id: number) => api.get<AuditLog>(`/audit/${id}`),
}
