import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { dashboardApi, DashboardStats, Reconciliation } from '../api/client'
import clsx from 'clsx'

const STATUS_LABELS: Record<string, string> = {
  pending: 'Pending',
  in_progress: 'In Progress',
  awaiting_approval: 'Awaiting Approval',
  approved: 'Approved',
  rejected: 'Rejected',
}

const STATUS_COLORS: Record<string, string> = {
  pending: 'badge-pending',
  in_progress: 'badge-open',
  awaiting_approval: 'badge-open',
  approved: 'badge-approved',
  rejected: 'badge-rejected',
}

function formatPeriod(start: string, end: string) {
  const s = new Date(start + 'T00:00:00')
  return s.toLocaleString('en-US', { month: 'long', year: 'numeric' })
}

function formatCurrency(value: string | null) {
  if (!value) return '—'
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
  }).format(parseFloat(value))
}

function StatCard({
  label,
  value,
  sub,
  highlight,
}: {
  label: string
  value: string | number
  sub?: string
  highlight?: boolean
}) {
  return (
    <div className={clsx('card', highlight && 'border-blue-200 bg-blue-50')}>
      <div className="text-xs text-gray-500 mb-1">{label}</div>
      <div className={clsx('text-2xl font-bold', highlight ? 'text-blue-700' : 'text-gray-900')}>
        {value}
      </div>
      {sub && <div className="text-xs text-gray-400 mt-0.5">{sub}</div>}
    </div>
  )
}

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    dashboardApi
      .get()
      .then((res) => setStats(res.data))
      .catch(() => setError('Failed to load dashboard'))
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div className="p-8 flex items-center justify-center min-h-[400px]">
        <div className="text-gray-400 text-sm">Loading dashboard…</div>
      </div>
    )
  }

  if (error || !stats) {
    return (
      <div className="p-8 text-red-600 text-sm">{error || 'No data.'}</div>
    )
  }

  return (
    <div className="p-8 max-w-6xl">
      {/* Header */}
      <div className="mb-8">
        <div className="text-xs font-semibold tracking-widest text-blue-600 uppercase mb-1">
          Reconciliation Workspace
        </div>
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <p className="text-sm text-gray-500 mt-1">October 2024 close · Operating Account ****4567</p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <StatCard label="Bank accounts" value={stats.total_accounts} />
        <StatCard label="Active reconciliations" value={stats.active_reconciliations} highlight />
        <StatCard
          label="Open exceptions"
          value={stats.exceptions_open}
          sub="Needs review"
        />
        <StatCard
          label="Match rate"
          value={`${stats.match_rate}%`}
          sub={`${stats.matches_this_month} transactions matched`}
        />
      </div>

      {/* Reconciliations table */}
      <div className="card p-0 overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-gray-900">Reconciliations</h2>
          <Link to="/app/exceptions" className="text-xs text-blue-600 hover:underline">
            View exceptions →
          </Link>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-100">
                <th className="text-left text-xs font-medium text-gray-500 px-5 py-3">Account</th>
                <th className="text-left text-xs font-medium text-gray-500 px-5 py-3">Period</th>
                <th className="text-left text-xs font-medium text-gray-500 px-5 py-3">Status</th>
                <th className="text-right text-xs font-medium text-gray-500 px-5 py-3">Transactions</th>
                <th className="text-right text-xs font-medium text-gray-500 px-5 py-3">Exceptions</th>
                <th className="text-right text-xs font-medium text-gray-500 px-5 py-3">Bank balance</th>
                <th className="text-right text-xs font-medium text-gray-500 px-5 py-3">Ledger balance</th>
                <th className="text-right text-xs font-medium text-gray-500 px-5 py-3">Difference</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {stats.reconciliations.map((r: Reconciliation) => {
                const diff =
                  r.bank_balance && r.ledger_balance
                    ? parseFloat(r.bank_balance) - parseFloat(r.ledger_balance)
                    : null
                return (
                  <tr key={r.id} className="hover:bg-gray-50 transition-colors">
                    <td className="px-5 py-3.5 font-medium text-gray-900">
                      {r.bank_account?.name ?? '—'}
                      <div className="text-xs text-gray-400 font-normal">
                        {r.bank_account?.masked_number}
                      </div>
                    </td>
                    <td className="px-5 py-3.5 text-gray-600">
                      {formatPeriod(r.period_start, r.period_end)}
                    </td>
                    <td className="px-5 py-3.5">
                      <span className={clsx(STATUS_COLORS[r.status] ?? 'badge-pending')}>
                        {STATUS_LABELS[r.status] ?? r.status}
                      </span>
                    </td>
                    <td className="px-5 py-3.5 text-right text-gray-600">{r.total_transactions}</td>
                    <td className="px-5 py-3.5 text-right">
                      {r.exception_count > 0 ? (
                        <span className="text-amber-700 font-medium">{r.exception_count}</span>
                      ) : (
                        <span className="text-gray-400">0</span>
                      )}
                    </td>
                    <td className="px-5 py-3.5 text-right text-gray-600 font-mono text-xs">
                      {formatCurrency(r.bank_balance)}
                    </td>
                    <td className="px-5 py-3.5 text-right text-gray-600 font-mono text-xs">
                      {formatCurrency(r.ledger_balance)}
                    </td>
                    <td className="px-5 py-3.5 text-right font-mono text-xs">
                      {diff !== null ? (
                        <span className={clsx(Math.abs(diff) > 0.01 ? 'text-red-600' : 'text-green-600')}>
                          {diff >= 0 ? '+' : ''}{diff.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                        </span>
                      ) : '—'}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Quick actions */}
      <div className="mt-6 flex gap-3">
        <Link to="/app/exceptions" className="btn-primary text-sm">
          Review exceptions ({stats.exceptions_open})
        </Link>
        <Link to="/app/audit" className="btn-secondary text-sm">
          View audit trail
        </Link>
      </div>
    </div>
  )
}
