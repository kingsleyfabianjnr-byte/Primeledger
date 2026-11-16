import { useEffect, useState } from 'react'
import { contractsApi, Contract, ContractStatus } from '../api/client'
import clsx from 'clsx'

const STATUS_LABELS: Record<ContractStatus, string> = {
  active: 'Active',
  completed: 'Completed',
  suspended: 'Suspended',
  overrun: 'Overrun',
}

const STATUS_COLORS: Record<ContractStatus, string> = {
  active: 'bg-green-100 text-green-800',
  completed: 'bg-gray-100 text-gray-700',
  suspended: 'bg-yellow-100 text-yellow-800',
  overrun: 'bg-red-100 text-red-800',
}

function formatCurrency(val: string | null, currency = 'USD') {
  if (!val) return '—'
  return new Intl.NumberFormat('en-US', { style: 'currency', currency }).format(parseFloat(val))
}

function formatDate(d: string | null) {
  if (!d) return '—'
  return new Date(d + 'T00:00:00').toLocaleDateString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric',
  })
}

// ── Utilization bar ───────────────────────────────────────────────────────────

function UtilizationBar({ pct, overrun }: { pct: number; overrun: boolean }) {
  const capped = Math.min(pct, 100)
  const color = overrun ? 'bg-red-500' : pct >= 90 ? 'bg-amber-500' : 'bg-blue-500'
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
        <div className={clsx('h-full rounded-full transition-all', color)} style={{ width: `${capped}%` }} />
      </div>
      <span className={clsx('text-xs font-mono tabular-nums', overrun ? 'text-red-600' : 'text-gray-600')}>
        {pct.toFixed(1)}%
      </span>
    </div>
  )
}

// ── Contract detail panel ────────────────────────────────────────────────────

function ContractDetail({ contract, onClose }: { contract: Contract; onClose: () => void }) {
  const remaining = parseFloat(contract.remaining_balance)
  const deployed = parseFloat(contract.deployed_amount)
  const used = parseFloat(contract.used_amount)
  const isOverrun = used > deployed

  return (
    <div className="fixed inset-0 bg-black/40 flex items-start justify-end z-50">
      <div className="bg-white w-full max-w-lg h-full overflow-y-auto shadow-xl">
        {/* Header */}
        <div className="sticky top-0 bg-white border-b border-gray-100 px-6 py-4 flex items-center justify-between">
          <div>
            <div className="text-xs text-gray-400 font-mono">{contract.reference}</div>
            <h2 className="text-base font-semibold text-gray-900">{contract.name}</h2>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-700 text-xl leading-none">×</button>
        </div>

        <div className="p-6 space-y-6">
          {/* Status + counterparty */}
          <div className="flex items-center gap-3">
            <span className={clsx('inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold', STATUS_COLORS[contract.status])}>
              {STATUS_LABELS[contract.status]}
            </span>
            <span className="text-sm text-gray-600">{contract.counterparty}</span>
            <span className="text-xs text-gray-400">{contract.currency}</span>
          </div>

          {/* Fund balance summary */}
          <div className="bg-gray-50 rounded-xl p-4 border border-gray-100">
            <div className="text-xs text-gray-400 uppercase tracking-wide mb-3">Fund balance</div>
            <div className="grid grid-cols-3 gap-4 mb-4">
              <div>
                <div className="text-xs text-gray-500 mb-0.5">Deployed</div>
                <div className="text-sm font-bold text-gray-900">{formatCurrency(contract.deployed_amount, contract.currency)}</div>
              </div>
              <div>
                <div className="text-xs text-gray-500 mb-0.5">Used</div>
                <div className={clsx('text-sm font-bold', isOverrun ? 'text-red-600' : 'text-gray-900')}>
                  {formatCurrency(contract.used_amount, contract.currency)}
                </div>
              </div>
              <div>
                <div className="text-xs text-gray-500 mb-0.5">Remaining</div>
                <div className={clsx('text-sm font-bold', remaining < 0 ? 'text-red-600' : 'text-green-700')}>
                  {formatCurrency(contract.remaining_balance, contract.currency)}
                </div>
              </div>
            </div>
            <UtilizationBar pct={contract.utilization_pct} overrun={isOverrun} />
            {isOverrun && (
              <div className="mt-2 text-xs text-red-600 font-medium">
                ⚠ Payments have exceeded the deployed fund — overrun of {formatCurrency(String(used - deployed), contract.currency)}
              </div>
            )}
          </div>

          {/* Schedule */}
          <div>
            <div className="text-xs text-gray-400 uppercase tracking-wide mb-2">Payment schedule</div>
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div>
                <span className="text-gray-500">Start: </span>
                <span className="text-gray-900">{formatDate(contract.contract_start)}</span>
              </div>
              <div>
                <span className="text-gray-500">End: </span>
                <span className="text-gray-900">{formatDate(contract.contract_end)}</span>
              </div>
              {contract.scheduled_payment_amount && (
                <div>
                  <span className="text-gray-500">Amount: </span>
                  <span className="text-gray-900 font-medium">
                    {formatCurrency(contract.scheduled_payment_amount, contract.currency)}
                    {contract.payment_frequency && ` / ${contract.payment_frequency}`}
                  </span>
                </div>
              )}
            </div>
          </div>

          {/* Description */}
          {contract.description && (
            <div>
              <div className="text-xs text-gray-400 uppercase tracking-wide mb-1">Description</div>
              <p className="text-sm text-gray-600 leading-relaxed">{contract.description}</p>
            </div>
          )}

          {/* Payment history */}
          {contract.payments && contract.payments.length > 0 && (
            <div>
              <div className="text-xs text-gray-400 uppercase tracking-wide mb-2">
                Payment history ({contract.payments.length})
              </div>
              <div className="space-y-2">
                {contract.payments
                  .slice()
                  .sort((a, b) => (a.period_month ?? '').localeCompare(b.period_month ?? ''))
                  .map((p) => (
                    <div key={p.id} className="flex items-center justify-between text-sm border border-gray-100 rounded-lg px-3 py-2.5">
                      <div>
                        <div className="font-medium text-gray-900">
                          {p.period_month
                            ? new Date(p.period_month + 'T00:00:00').toLocaleDateString('en-US', { month: 'long', year: 'numeric' })
                            : '—'}
                        </div>
                        {p.notes && <div className="text-xs text-gray-400">{p.notes}</div>}
                      </div>
                      <div className="text-right">
                        <div className={clsx(
                          'inline-flex items-center px-2 py-0.5 rounded text-xs font-medium',
                          p.status === 'matched' ? 'bg-green-100 text-green-800' :
                          p.status === 'partial' ? 'bg-yellow-100 text-yellow-800' :
                          p.status === 'overdue' ? 'bg-red-100 text-red-800' :
                          'bg-gray-100 text-gray-700'
                        )}>
                          {p.status}
                        </div>
                        <div className="text-xs text-gray-600 mt-0.5">
                          {p.actual_amount
                            ? formatCurrency(p.actual_amount, contract.currency)
                            : p.expected_amount
                            ? `Expected ${formatCurrency(p.expected_amount, contract.currency)}`
                            : '—'}
                        </div>
                      </div>
                    </div>
                  ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Contracts Page ────────────────────────────────────────────────────────────

export default function ContractsPage() {
  const [contracts, setContracts] = useState<Contract[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [selected, setSelected] = useState<Contract | null>(null)
  const [filterStatus, setFilterStatus] = useState<ContractStatus | 'all'>('all')

  useEffect(() => {
    contractsApi
      .list()
      .then((res) => setContracts(res.data))
      .catch(() => setError('Failed to load contracts'))
      .finally(() => setLoading(false))
  }, [])

  const filtered = filterStatus === 'all'
    ? contracts
    : contracts.filter((c) => c.status === filterStatus)

  const totalDeployed = contracts.reduce((s, c) => s + parseFloat(c.deployed_amount), 0)
  const totalUsed = contracts.reduce((s, c) => s + parseFloat(c.used_amount), 0)
  const overrunCount = contracts.filter((c) => c.status === 'overrun').length
  const activeCount = contracts.filter((c) => c.status === 'active').length

  if (loading) {
    return (
      <div className="p-8 flex items-center justify-center min-h-[400px]">
        <div className="text-gray-400 text-sm">Loading contracts…</div>
      </div>
    )
  }

  return (
    <div className="p-8 max-w-6xl">
      {/* Header */}
      <div className="mb-8">
        <div className="text-xs font-semibold tracking-widest text-blue-600 uppercase mb-1">
          Fund Management
        </div>
        <h1 className="text-2xl font-bold text-gray-900">Contracts</h1>
        <p className="text-sm text-gray-500 mt-1">
          Track deployed funds, monthly payment drawdowns, and contract balances.
          Each payment is verified against the reconciliation to prevent overruns.
        </p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <div className="card">
          <div className="text-xs text-gray-500 mb-1">Active contracts</div>
          <div className="text-2xl font-bold text-blue-700">{activeCount}</div>
        </div>
        <div className="card">
          <div className="text-xs text-gray-500 mb-1">Total deployed</div>
          <div className="text-2xl font-bold text-gray-900">
            {new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', notation: 'compact', maximumFractionDigits: 1 }).format(totalDeployed)}
          </div>
        </div>
        <div className="card">
          <div className="text-xs text-gray-500 mb-1">Total used</div>
          <div className="text-2xl font-bold text-gray-900">
            {new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', notation: 'compact', maximumFractionDigits: 1 }).format(totalUsed)}
          </div>
        </div>
        <div className={clsx('card', overrunCount > 0 && 'border-red-200 bg-red-50')}>
          <div className="text-xs text-gray-500 mb-1">Overrun alerts</div>
          <div className={clsx('text-2xl font-bold', overrunCount > 0 ? 'text-red-700' : 'text-gray-400')}>
            {overrunCount}
          </div>
        </div>
      </div>

      {/* Filter tabs */}
      <div className="flex items-center gap-1 mb-5 border-b border-gray-200 pb-2">
        {(['all', 'active', 'completed', 'overrun', 'suspended'] as const).map((f) => (
          <button
            key={f}
            onClick={() => setFilterStatus(f)}
            className={clsx(
              'px-3 py-1.5 text-xs font-medium rounded-lg transition-colors',
              filterStatus === f
                ? 'bg-blue-50 text-blue-700'
                : 'text-gray-500 hover:text-gray-900 hover:bg-gray-100'
            )}
          >
            {f === 'all' ? `All (${contracts.length})` : f.charAt(0).toUpperCase() + f.slice(1)}
          </button>
        ))}
      </div>

      {error && <div className="text-sm text-red-600 mb-4">{error}</div>}

      {filtered.length === 0 ? (
        <div className="text-center py-16 text-gray-400 text-sm">No contracts match this filter.</div>
      ) : (
        <div className="card p-0 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-100">
                <th className="text-left text-xs font-medium text-gray-500 px-5 py-3">Reference</th>
                <th className="text-left text-xs font-medium text-gray-500 px-5 py-3">Counterparty</th>
                <th className="text-left text-xs font-medium text-gray-500 px-5 py-3">Status</th>
                <th className="text-right text-xs font-medium text-gray-500 px-5 py-3">Deployed</th>
                <th className="text-right text-xs font-medium text-gray-500 px-5 py-3">Used</th>
                <th className="text-right text-xs font-medium text-gray-500 px-5 py-3">Remaining</th>
                <th className="text-left text-xs font-medium text-gray-500 px-5 py-3 w-40">Utilization</th>
                <th className="text-left text-xs font-medium text-gray-500 px-5 py-3">Schedule</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {filtered.map((c) => {
                const isOverrun = c.status === 'overrun'
                return (
                  <tr
                    key={c.id}
                    className="hover:bg-gray-50 transition-colors cursor-pointer"
                    onClick={() => setSelected(c)}
                  >
                    <td className="px-5 py-3.5">
                      <div className="font-medium text-blue-700 hover:underline">{c.reference}</div>
                      <div className="text-xs text-gray-400">{c.name}</div>
                    </td>
                    <td className="px-5 py-3.5 text-gray-700">{c.counterparty}</td>
                    <td className="px-5 py-3.5">
                      <span className={clsx('inline-flex items-center px-2 py-0.5 rounded text-xs font-medium', STATUS_COLORS[c.status])}>
                        {STATUS_LABELS[c.status]}
                      </span>
                    </td>
                    <td className="px-5 py-3.5 text-right font-mono text-xs text-gray-700">
                      {formatCurrency(c.deployed_amount, c.currency)}
                    </td>
                    <td className="px-5 py-3.5 text-right font-mono text-xs text-gray-700">
                      {formatCurrency(c.used_amount, c.currency)}
                    </td>
                    <td className={clsx('px-5 py-3.5 text-right font-mono text-xs font-medium', isOverrun ? 'text-red-600' : 'text-green-700')}>
                      {formatCurrency(c.remaining_balance, c.currency)}
                    </td>
                    <td className="px-5 py-3.5 w-40">
                      <UtilizationBar pct={c.utilization_pct} overrun={isOverrun} />
                    </td>
                    <td className="px-5 py-3.5 text-xs text-gray-500">
                      {c.scheduled_payment_amount && c.payment_frequency
                        ? `${formatCurrency(c.scheduled_payment_amount, c.currency)} / ${c.payment_frequency}`
                        : '—'}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* How contract reconciliation works */}
      <div className="mt-8 p-5 bg-blue-50 border border-blue-100 rounded-xl">
        <div className="text-xs font-semibold text-blue-700 uppercase tracking-wide mb-2">How contract matching works</div>
        <div className="grid md:grid-cols-3 gap-4 text-xs text-blue-900">
          <div>
            <div className="font-semibold mb-1">1. Fund deployment</div>
            When a contract is signed, the initial payment is logged as the deployed amount.
            Every subsequent payment must draw down from this balance.
          </div>
          <div>
            <div className="font-semibold mb-1">2. Monthly drawdown matching</div>
            Each bank statement entry (e.g. a $70,000 monthly payment) is matched to the
            contract schedule. Amount, period, and reference are verified automatically.
          </div>
          <div>
            <div className="font-semibold mb-1">3. Variance exceptions</div>
            If a payment differs from the scheduled amount, a <em>contract_variance</em> exception
            is raised in the queue. Overruns are flagged immediately as Critical severity.
          </div>
        </div>
      </div>

      {/* Detail panel */}
      {selected && <ContractDetail contract={selected} onClose={() => setSelected(null)} />}
    </div>
  )
}
