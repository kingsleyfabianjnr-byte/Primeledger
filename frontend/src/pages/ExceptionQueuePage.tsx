import { useEffect, useState } from 'react'
import { exceptionsApi, Exception, ExceptionStatus } from '../api/client'
import { useAuth } from '../contexts/AuthContext'
import clsx from 'clsx'

const TYPE_LABELS: Record<string, string> = {
  timing: 'Timing',
  duplicate: 'Duplicate',
  missing_entry: 'Missing entry',
  amount_mismatch: 'Amount mismatch',
  fx: 'FX difference',
}

const TYPE_COLORS: Record<string, string> = {
  timing: 'bg-blue-100 text-blue-800',
  duplicate: 'bg-purple-100 text-purple-800',
  missing_entry: 'bg-amber-100 text-amber-800',
  amount_mismatch: 'bg-red-100 text-red-800',
  fx: 'bg-teal-100 text-teal-800',
}

function ConfidenceBar({ score }: { score: string }) {
  const val = parseFloat(score)
  const color = val >= 0.9 ? 'bg-green-500' : val >= 0.75 ? 'bg-yellow-500' : 'bg-red-500'
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-gray-200 rounded-full overflow-hidden">
        <div className={clsx('h-full rounded-full transition-all', color)} style={{ width: `${val * 100}%` }} />
      </div>
      <span className="text-xs text-gray-600 font-mono tabular-nums">{val.toFixed(2)}</span>
    </div>
  )
}

type ReviewAction = 'approve' | 'reject' | 'edit' | null

function formatAmount(val: string | null) {
  if (!val) return null
  const n = parseFloat(val)
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(n)
}

function ExceptionCard({
  exc,
  index,
  total,
  onReviewed,
}: {
  exc: Exception
  index: number
  total: number
  onReviewed: (updated: Exception) => void
}) {
  const { user } = useAuth()
  const [action, setAction] = useState<ReviewAction>(null)
  const [note, setNote] = useState('')
  const [editDebit, setEditDebit] = useState(exc.suggested_debit ?? '')
  const [editCredit, setEditCredit] = useState(exc.suggested_credit ?? '')
  const [editAmount, setEditAmount] = useState(exc.suggested_amount ?? '')
  const [submitting, setSubmitting] = useState(false)
  const [err, setErr] = useState('')

  const canApproveReject = user?.role === 'approver' || user?.role === 'admin'
  const isReviewed = exc.status !== 'open'

  const handleSubmit = async () => {
    if (!action) return
    setSubmitting(true)
    setErr('')
    try {
      const res = await exceptionsApi.review(exc.id, {
        action,
        reviewer_note: note,
        ...(action === 'edit'
          ? { suggested_debit: editDebit, suggested_credit: editCredit, suggested_amount: editAmount }
          : {}),
      })
      onReviewed(res.data)
      setAction(null)
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setErr(msg ?? 'Action failed. Try again.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className={clsx('card mb-4', isReviewed && 'opacity-60')}>
      {/* Card header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-400 font-mono">
            Exception {index + 1} of {total}
          </span>
          <span
            className={clsx(
              'inline-flex items-center px-2 py-0.5 rounded text-xs font-medium',
              TYPE_COLORS[exc.exception_type] ?? 'bg-gray-100 text-gray-700'
            )}
          >
            {TYPE_LABELS[exc.exception_type] ?? exc.exception_type}
          </span>
        </div>
        <span
          className={clsx(
            exc.status === 'open'
              ? 'badge-open'
              : exc.status === 'approved'
              ? 'badge-approved'
              : exc.status === 'rejected'
              ? 'badge-rejected'
              : 'badge-pending'
          )}
        >
          {exc.status.replace('_', ' ')}
        </span>
      </div>

      {/* Bank vs Ledger split */}
      <div className="grid grid-cols-2 gap-4 mb-4 p-4 bg-gray-50 rounded-lg border border-gray-100">
        <div>
          <div className="text-xs text-gray-400 uppercase tracking-wide mb-1">Bank statement</div>
          {exc.bank_date && (
            <div className="text-sm font-medium text-gray-900">
              {new Date(exc.bank_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
              {exc.bank_amount && ` · ${formatAmount(exc.bank_amount)}`}
            </div>
          )}
          {exc.bank_description && (
            <div className="text-xs text-gray-500 mt-0.5">{exc.bank_description}</div>
          )}
          {!exc.bank_date && !exc.bank_amount && (
            <div className="text-sm text-gray-500">—</div>
          )}
        </div>
        <div>
          <div className="text-xs text-gray-400 uppercase tracking-wide mb-1">General ledger</div>
          {exc.ledger_amount ? (
            <div className="text-sm font-medium text-gray-900">{formatAmount(exc.ledger_amount)}</div>
          ) : (
            <div className="text-sm font-medium text-red-500">No matching entry</div>
          )}
        </div>
      </div>

      {/* AI explanation */}
      <div className="bg-blue-50 border border-blue-100 rounded-lg p-3 mb-3">
        <div className="flex items-center gap-1.5 mb-1.5">
          <span className="text-xs font-semibold text-blue-600 bg-blue-100 rounded px-1.5 py-0.5">AI</span>
          <span className="text-xs text-blue-700 font-medium">Explanation</span>
        </div>
        <p className="text-xs text-blue-900 leading-relaxed">{exc.ai_explanation}</p>
      </div>

      {/* Confidence */}
      <div className="mb-3">
        <div className="text-xs text-gray-400 mb-1">Confidence</div>
        <ConfidenceBar score={exc.confidence_score} />
      </div>

      {/* Suggested journal entry */}
      {(exc.suggested_debit || exc.suggested_credit) && (
        <div className="bg-gray-50 rounded-lg p-3 mb-3 border border-gray-100">
          <div className="text-xs text-gray-400 mb-1.5">Suggested journal entry</div>
          {action === 'edit' ? (
            <div className="space-y-2">
              <div>
                <label className="label text-xs">Debit entry</label>
                <input
                  className="input text-xs font-mono"
                  value={editDebit}
                  onChange={(e) => setEditDebit(e.target.value)}
                />
              </div>
              <div>
                <label className="label text-xs">Credit entry</label>
                <input
                  className="input text-xs font-mono"
                  value={editCredit}
                  onChange={(e) => setEditCredit(e.target.value)}
                />
              </div>
              <div>
                <label className="label text-xs">Amount</label>
                <input
                  className="input text-xs font-mono"
                  value={editAmount}
                  onChange={(e) => setEditAmount(e.target.value)}
                  type="number"
                  step="0.01"
                />
              </div>
            </div>
          ) : (
            <div className="text-xs font-mono text-gray-700 space-y-1">
              {exc.suggested_debit && <div>{exc.suggested_debit}</div>}
              {exc.suggested_credit && <div>{exc.suggested_credit}</div>}
            </div>
          )}
        </div>
      )}

      {/* Review note */}
      {(action === 'approve' || action === 'reject') && (
        <div className="mb-3">
          <label className="label text-xs">Review note (optional)</label>
          <textarea
            className="input text-xs resize-none"
            rows={2}
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Add a note for the audit trail…"
          />
        </div>
      )}

      {err && <div className="text-xs text-red-600 mb-2">{err}</div>}

      {/* Actions */}
      {!isReviewed && (
        <div className="flex items-center gap-2 pt-1 border-t border-gray-100 mt-3">
          {action === null ? (
            <>
              {canApproveReject && (
                <button
                  onClick={() => setAction('approve')}
                  className="btn-primary text-xs px-4 py-1.5"
                >
                  Approve
                </button>
              )}
              <button
                onClick={() => setAction('edit')}
                className="btn-secondary text-xs px-4 py-1.5"
              >
                Edit
              </button>
              {canApproveReject && (
                <button
                  onClick={() => setAction('reject')}
                  className="btn-ghost text-xs px-3 py-1.5 text-red-600 hover:bg-red-50"
                >
                  Reject
                </button>
              )}
              {!canApproveReject && (
                <span className="text-xs text-gray-400 italic">Approver required to post</span>
              )}
            </>
          ) : (
            <>
              <button
                onClick={handleSubmit}
                disabled={submitting}
                className={clsx(
                  'text-xs px-4 py-1.5',
                  action === 'reject'
                    ? 'btn-ghost text-red-600 hover:bg-red-50'
                    : 'btn-primary'
                )}
              >
                {submitting ? 'Saving…' : `Confirm ${action}`}
              </button>
              <button onClick={() => setAction(null)} className="btn-secondary text-xs px-4 py-1.5">
                Cancel
              </button>
            </>
          )}
        </div>
      )}

      {isReviewed && exc.reviewer_note && (
        <div className="mt-3 pt-3 border-t border-gray-100 text-xs text-gray-500 italic">
          Note: {exc.reviewer_note}
        </div>
      )}
    </div>
  )
}

export default function ExceptionQueuePage() {
  const [exceptions, setExceptions] = useState<Exception[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<ExceptionStatus | 'all'>('all')
  const [error, setError] = useState('')

  useEffect(() => {
    exceptionsApi
      .list()
      .then((res) => setExceptions(res.data))
      .catch(() => setError('Failed to load exceptions'))
      .finally(() => setLoading(false))
  }, [])

  const handleReviewed = (updated: Exception) => {
    setExceptions((prev) => prev.map((e) => (e.id === updated.id ? updated : e)))
  }

  const filtered = filter === 'all' ? exceptions : exceptions.filter((e) => e.status === filter)
  const openCount = exceptions.filter((e) => e.status === 'open').length
  const approvedCount = exceptions.filter((e) => e.status === 'approved').length
  const rejectedCount = exceptions.filter((e) => e.status === 'rejected').length

  if (loading) {
    return (
      <div className="p-8 flex items-center justify-center min-h-[400px]">
        <div className="text-gray-400 text-sm">Loading exceptions…</div>
      </div>
    )
  }

  return (
    <div className="p-8 max-w-3xl">
      {/* Header */}
      <div className="mb-6">
        <div className="text-xs font-semibold tracking-widest text-blue-600 uppercase mb-1">
          October 2024 · Operating Account ****4567
        </div>
        <h1 className="text-2xl font-bold text-gray-900">
          Exception Queue
          {openCount > 0 && (
            <span className="ml-2 text-sm font-normal text-amber-700 bg-amber-100 rounded-full px-2 py-0.5">
              {openCount} open
            </span>
          )}
        </h1>
        <p className="text-sm text-gray-500 mt-1">
          Review AI-identified items. Only approvers can post entries.
        </p>
      </div>

      {/* Stats strip */}
      <div className="grid grid-cols-3 gap-3 mb-5">
        <div className="card py-3 px-4">
          <div className="text-xs text-gray-500 mb-0.5">Open</div>
          <div className="text-xl font-bold text-amber-700">{openCount}</div>
        </div>
        <div className="card py-3 px-4">
          <div className="text-xs text-gray-500 mb-0.5">Approved</div>
          <div className="text-xl font-bold text-green-700">{approvedCount}</div>
        </div>
        <div className="card py-3 px-4">
          <div className="text-xs text-gray-500 mb-0.5">Rejected</div>
          <div className="text-xl font-bold text-red-700">{rejectedCount}</div>
        </div>
      </div>

      {/* Filter tabs */}
      <div className="flex items-center gap-1 mb-5 border-b border-gray-200 pb-2">
        {(['all', 'open', 'approved', 'rejected'] as const).map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={clsx(
              'px-3 py-1.5 text-xs font-medium rounded-lg transition-colors',
              filter === f
                ? 'bg-blue-50 text-blue-700'
                : 'text-gray-500 hover:text-gray-900 hover:bg-gray-100'
            )}
          >
            {f === 'all'
              ? `All (${exceptions.length})`
              : f.charAt(0).toUpperCase() + f.slice(1)}
          </button>
        ))}
      </div>

      {error && <div className="text-sm text-red-600 mb-4">{error}</div>}

      {filtered.length === 0 ? (
        <div className="text-center py-16 text-gray-400 text-sm">
          No exceptions match this filter.
        </div>
      ) : (
        filtered.map((exc, i) => (
          <ExceptionCard
            key={exc.id}
            exc={exc}
            index={i}
            total={filtered.length}
            onReviewed={handleReviewed}
          />
        ))
      )}
    </div>
  )
}
