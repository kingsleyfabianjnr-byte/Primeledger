import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { dashboardApi, reconciliationsApi, contractsApi, DashboardStats, Reconciliation, Contract } from '../api/client'
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

function formatPeriod(start: string) {
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

// ── New Reconciliation Modal ──────────────────────────────────────────────────

function NewReconModal({
  onClose,
  onCreated,
}: {
  onClose: () => void
  onCreated: () => void
}) {
  const [accountId, setAccountId] = useState('1')
  const [periodStart, setPeriodStart] = useState('')
  const [periodEnd, setPeriodEnd] = useState('')
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState('')

  // Default to current month
  useEffect(() => {
    const now = new Date()
    const y = now.getFullYear()
    const m = String(now.getMonth() + 1).padStart(2, '0')
    const lastDay = new Date(y, now.getMonth() + 1, 0).getDate()
    setPeriodStart(`${y}-${m}-01`)
    setPeriodEnd(`${y}-${m}-${lastDay}`)
  }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setErr('')
    setLoading(true)
    try {
      await reconciliationsApi.create({
        bank_account_id: parseInt(accountId),
        period_start: periodStart,
        period_end: periodEnd,
      })
      onCreated()
      onClose()
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setErr(msg ?? 'Failed to create reconciliation.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-sm">
        <div className="px-6 py-5 border-b border-gray-100">
          <h2 className="text-base font-semibold text-gray-900">Start new reconciliation</h2>
          <p className="text-xs text-gray-500 mt-0.5">
            Creates a new reconciliation run for the selected account and period.
          </p>
        </div>
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <div>
            <label className="label">Bank account</label>
            <select
              className="input"
              value={accountId}
              onChange={(e) => setAccountId(e.target.value)}
            >
              <option value="1">Operating Account ****4567</option>
              <option value="2">Payroll Account ****4890</option>
              <option value="3">Reserve Account ****1122</option>
            </select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">Period start</label>
              <input
                type="date"
                className="input"
                value={periodStart}
                onChange={(e) => setPeriodStart(e.target.value)}
                required
              />
            </div>
            <div>
              <label className="label">Period end</label>
              <input
                type="date"
                className="input"
                value={periodEnd}
                onChange={(e) => setPeriodEnd(e.target.value)}
                required
              />
            </div>
          </div>
          {err && <div className="text-xs text-red-600">{err}</div>}
          <div className="flex gap-3 pt-1">
            <button type="submit" disabled={loading} className="btn-primary flex-1">
              {loading ? 'Starting…' : 'Start reconciliation'}
            </button>
            <button type="button" onClick={onClose} className="btn-secondary">
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ── Dashboard Page ────────────────────────────────────────────────────────────

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [contracts, setContracts] = useState<Contract[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [showNewRecon, setShowNewRecon] = useState(false)

  const load = () => {
    setLoading(true)
    Promise.all([
      dashboardApi.get(),
      contractsApi.list({ active_only: true }),
    ])
      .then(([dashRes, ctrRes]) => {
        setStats(dashRes.data)
        setContracts(ctrRes.data)
      })
      .catch(() => setError('Failed to load dashboard'))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  if (loading) {
    return (
      <div className="p-8 flex items-center justify-center min-h-[400px]">
        <div className="text-gray-400 text-sm">Loading dashboard…</div>
      </div>
    )
  }

  if (error || !stats) {
    return <div className="p-8 text-red-600 text-sm">{error || 'No data.'}</div>
  }

  // Derive a human-readable period from the most recent in-progress reconciliation
  const activeRecon = stats.reconciliations.find((r) => r.status === 'in_progress')
  const periodLabel = activeRecon
    ? formatPeriod(activeRecon.period_start)
    : 'No active reconciliation'
  const accountLabel = activeRecon?.bank_account?.masked_number
    ? `${activeRecon.bank_account.name} ${activeRecon.bank_account.masked_number}`
    : ''

  return (
    <div className="p-8 max-w-6xl">
      {/* Header */}
      <div className="mb-8 flex items-start justify-between gap-4">
        <div>
          <div className="text-xs font-semibold tracking-widest text-blue-600 uppercase mb-1">
            Reconciliation Workspace
          </div>
          <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
          {activeRecon && (
            <p className="text-sm text-gray-500 mt-1">
              {periodLabel}
              {accountLabel && ` · ${accountLabel}`}
            </p>
          )}
        </div>
        <button
          onClick={() => setShowNewRecon(true)}
          className="btn-primary text-sm shrink-0 mt-1"
        >
          + New reconciliation
        </button>
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
                      {formatPeriod(r.period_start)}
                    </td>
                    <td className="px-5 py-3.5">
                      <span className={clsx(STATUS_COLORS[r.status] ?? 'badge-pending')}>
                        {STATUS_LABELS[r.status] ?? r.status}
                      </span>
                    </td>
                    <td className="px-5 py-3.5 text-right text-gray-600">{r.total_transactions}</td>
                    <td className="px-5 py-3.5 text-right">
                      {r.exception_count > 0 ? (
                        <Link
                          to="/app/exceptions"
                          className="text-amber-700 font-medium hover:underline"
                        >
                          {r.exception_count}
                        </Link>
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
                        <span
                          className={clsx(
                            Math.abs(diff) > 0.01 ? 'text-red-600' : 'text-green-600'
                          )}
                        >
                          {diff >= 0 ? '+' : ''}
                          {diff.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                        </span>
                      ) : (
                        '—'
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Active contracts widget */}
      {contracts.length > 0 && (
        <div className="mt-6 card p-0 overflow-hidden">
          <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-gray-900">Active contracts</h2>
            <Link to="/app/contracts" className="text-xs text-blue-600 hover:underline">
              View all →
            </Link>
          </div>
          <div className="divide-y divide-gray-50">
            {contracts.slice(0, 3).map((c) => {
              const isOverrun = parseFloat(c.used_amount) > parseFloat(c.deployed_amount)
              return (
                <div key={c.id} className="px-5 py-3 flex items-center justify-between">
                  <div>
                    <div className="text-sm font-medium text-gray-900">{c.name}</div>
                    <div className="text-xs text-gray-400">{c.reference} · {c.counterparty}</div>
                  </div>
                  <div className="text-right">
                    <div className={clsx('text-sm font-mono font-medium', isOverrun ? 'text-red-600' : 'text-green-700')}>
                      {new Intl.NumberFormat('en-US', { style: 'currency', currency: c.currency }).format(parseFloat(c.remaining_balance))} remaining
                    </div>
                    <div className="text-xs text-gray-400">
                      of {new Intl.NumberFormat('en-US', { style: 'currency', currency: c.currency }).format(parseFloat(c.deployed_amount))} deployed
                      {c.scheduled_payment_amount && ` · ${new Intl.NumberFormat('en-US', { style: 'currency', currency: c.currency }).format(parseFloat(c.scheduled_payment_amount))}/mo`}
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Quick actions */}
      <div className="mt-6 flex gap-3">
        <Link to="/app/exceptions" className="btn-primary text-sm">
          Review exceptions ({stats.exceptions_open})
        </Link>
        <Link to="/app/audit" className="btn-secondary text-sm">
          View audit trail
        </Link>
        <Link to="/app/contracts" className="btn-secondary text-sm">
          Contracts
        </Link>
        <Link to="/app/import" className="btn-secondary text-sm">
          Import CSV
        </Link>
      </div>

      {/* New reconciliation modal */}
      {showNewRecon && (
        <NewReconModal
          onClose={() => setShowNewRecon(false)}
          onCreated={load}
        />
      )}
    </div>
  )
}
