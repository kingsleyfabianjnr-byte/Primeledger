import React, { useEffect, useState } from 'react'
import { auditApi, exportApi, AuditLog, AuditAction } from '../api/client'
import clsx from 'clsx'

const ACTION_LABELS: Record<AuditAction, string> = {
  match_created: 'Match created',
  exception_raised: 'Exception raised',
  entry_approved: 'Entry approved',
  entry_rejected: 'Entry rejected',
  entry_edited: 'Entry edited',
  reconciliation_started: 'Reconciliation started',
  reconciliation_completed: 'Reconciliation completed',
  user_logged_in: 'User logged in',
}

const ACTION_COLORS: Record<AuditAction, string> = {
  match_created: 'bg-green-100 text-green-800',
  exception_raised: 'bg-amber-100 text-amber-800',
  entry_approved: 'bg-green-100 text-green-800',
  entry_rejected: 'bg-red-100 text-red-800',
  entry_edited: 'bg-blue-100 text-blue-800',
  reconciliation_started: 'bg-purple-100 text-purple-800',
  reconciliation_completed: 'bg-purple-100 text-purple-800',
  user_logged_in: 'bg-gray-100 text-gray-700',
}

function truncateHash(hash: string) {
  return hash.slice(0, 8) + '…' + hash.slice(-8)
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  setTimeout(() => {
    URL.revokeObjectURL(url)
    document.body.removeChild(a)
  }, 100)
}

export default function AuditTrailPage() {
  const [logs, setLogs] = useState<AuditLog[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [expanded, setExpanded] = useState<number | null>(null)
  const [exporting, setExporting] = useState<'csv' | 'excel' | null>(null)

  useEffect(() => {
    auditApi
      .list({ limit: 200 })
      .then((res) => setLogs(res.data))
      .catch(() => setError('Failed to load audit trail'))
      .finally(() => setLoading(false))
  }, [])

  const handleExport = async (format: 'csv' | 'excel') => {
    setExporting(format)
    try {
      const res = format === 'csv' ? await exportApi.auditCsv() : await exportApi.auditExcel()
      const ext = format === 'csv' ? 'csv' : 'xlsx'
      downloadBlob(res.data as Blob, `audit_trail.${ext}`)
    } catch {
      setError('Export failed — please try again.')
    } finally {
      setExporting(null)
    }
  }

  if (loading) {
    return (
      <div className="p-8 flex items-center justify-center min-h-[400px]">
        <div className="text-gray-400 text-sm">Loading audit trail…</div>
      </div>
    )
  }

  return (
    <div className="p-8 max-w-5xl">
      {/* Header */}
      <div className="mb-8 flex items-start justify-between gap-4">
        <div>
          <div className="text-xs font-semibold tracking-widest text-blue-600 uppercase mb-1">
            Tamper-evident log
          </div>
          <h1 className="text-2xl font-bold text-gray-900">Audit Trail</h1>
          <p className="text-sm text-gray-500 mt-1">
            Every action by every person and agent. Hash-linked entries — any modification is detectable.
          </p>
        </div>
        {/* Export buttons */}
        <div className="flex items-center gap-2 shrink-0 mt-1">
          <button
            onClick={() => handleExport('csv')}
            disabled={exporting !== null}
            className="btn-secondary text-xs"
          >
            {exporting === 'csv' ? 'Exporting…' : '↓ Export CSV'}
          </button>
          <button
            onClick={() => handleExport('excel')}
            disabled={exporting !== null}
            className="btn-secondary text-xs"
          >
            {exporting === 'excel' ? 'Exporting…' : '↓ Export Excel'}
          </button>
        </div>
      </div>

      {/* Stats strip */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        {[
          { label: 'Total entries', value: logs.length },
          {
            label: 'AI actions',
            value: logs.filter((l) => l.user_id === null).length,
          },
          {
            label: 'Human actions',
            value: logs.filter((l) => l.user_id !== null).length,
          },
          {
            label: 'Chain intact',
            value: logs.length > 0 ? '✓ Verified' : '—',
          },
        ].map((s) => (
          <div key={s.label} className="card py-3 px-4">
            <div className="text-xs text-gray-500 mb-0.5">{s.label}</div>
            <div className="text-lg font-bold text-gray-900">{s.value}</div>
          </div>
        ))}
      </div>

      {error && <div className="text-sm text-red-600 mb-4">{error}</div>}

      {logs.length === 0 ? (
        <div className="text-center py-16 text-gray-400 text-sm">No audit log entries found.</div>
      ) : (
        <div className="card p-0 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-100">
                <th className="text-left text-xs font-medium text-gray-500 px-4 py-3 w-8">#</th>
                <th className="text-left text-xs font-medium text-gray-500 px-4 py-3">Timestamp</th>
                <th className="text-left text-xs font-medium text-gray-500 px-4 py-3">Action</th>
                <th className="text-left text-xs font-medium text-gray-500 px-4 py-3">Entity</th>
                <th className="text-left text-xs font-medium text-gray-500 px-4 py-3">By</th>
                <th className="text-left text-xs font-medium text-gray-500 px-4 py-3">Hash</th>
                <th className="text-left text-xs font-medium text-gray-500 px-4 py-3">Chain</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {logs.map((log) => (
                <React.Fragment key={log.id}>
                  <tr
                    className="hover:bg-gray-50 transition-colors cursor-pointer"
                    onClick={() => setExpanded(expanded === log.id ? null : log.id)}
                  >
                    <td className="px-4 py-3 text-xs text-gray-400 font-mono">{log.id}</td>
                    <td className="px-4 py-3 text-xs text-gray-600 whitespace-nowrap">
                      {formatDate(log.created_at)}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={clsx(
                          'inline-flex items-center px-2 py-0.5 rounded text-xs font-medium',
                          ACTION_COLORS[log.action]
                        )}
                      >
                        {ACTION_LABELS[log.action] ?? log.action}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-600">
                      {log.entity_type}
                      {log.entity_id ? ` #${log.entity_id}` : ''}
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-600">
                      {log.user_id ? (
                        `User #${log.user_id}`
                      ) : (
                        <span className="text-blue-600 italic">AI agent</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className="text-xs font-mono text-gray-500 bg-gray-100 rounded px-2 py-0.5"
                        title={log.entry_hash}
                      >
                        {truncateHash(log.entry_hash)}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      {log.previous_hash ? (
                        <span className="text-xs text-green-600 font-medium">✓ chained</span>
                      ) : (
                        <span className="text-xs text-gray-400">genesis</span>
                      )}
                    </td>
                  </tr>
                  {expanded === log.id && (
                    <tr key={`${log.id}-detail`} className="bg-gray-50">
                      <td colSpan={7} className="px-4 py-4">
                        <div className="text-xs font-semibold text-gray-500 mb-1.5">Entry details</div>
                        {log.details && (
                          <pre className="text-xs font-mono text-gray-700 bg-white border border-gray-200 rounded-lg p-3 overflow-x-auto mb-2">
                            {JSON.stringify(log.details, null, 2)}
                          </pre>
                        )}
                        <div className="text-xs text-gray-400 font-mono space-y-0.5">
                          <div>
                            <span className="font-semibold text-gray-600">Entry hash: </span>
                            {log.entry_hash}
                          </div>
                          {log.previous_hash && (
                            <div>
                              <span className="font-semibold text-gray-600">Previous hash: </span>
                              {log.previous_hash}
                            </div>
                          )}
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Tamper-evident note */}
      <div className="mt-6 p-4 bg-gray-50 border border-gray-200 rounded-xl text-xs text-gray-500">
        <strong className="text-gray-700">Tamper-evident:</strong> Each entry's SHA-256 hash includes
        the previous entry's hash. Any modification to a past entry invalidates the entire subsequent
        chain, making it immediately detectable.
      </div>
    </div>
  )
}
