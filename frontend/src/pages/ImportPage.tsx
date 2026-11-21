import { useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import clsx from 'clsx'

interface ImportResult {
  reconciliation_id: number
  account: string
  period: string
  rows_imported: number
  rows_skipped: number
  matched: number
  exceptions: number
  message: string
}

export default function ImportPage() {
  const navigate = useNavigate()
  const fileRef = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [accountId, setAccountId] = useState('1')
  const [periodStart, setPeriodStart] = useState('')
  const [periodEnd, setPeriodEnd] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<ImportResult | null>(null)
  const [error, setError] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!file) { setError('Please select a CSV file'); return }
    if (!periodStart || !periodEnd) { setError('Please set the period dates'); return }

    setLoading(true)
    setError('')
    setResult(null)

    const form = new FormData()
    form.append('file', file)
    form.append('bank_account_id', accountId)
    form.append('period_start', periodStart)
    form.append('period_end', periodEnd)

    try {
      // Let browser set Content-Type automatically (needs to include multipart boundary)
      const importApi = axios.create({
        baseURL: import.meta.env.VITE_API_URL
          ? `${import.meta.env.VITE_API_URL}/api`
          : '/api',
      })
      const token = localStorage.getItem('pl_token')
      const res = await importApi.post('/import/bank-statement', form, {
        headers: { Authorization: `Bearer ${token}` },
      })
      setResult(res.data)
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } | string }; message?: string }
      const detail = err?.response?.data
      const msg = typeof detail === 'object' ? detail?.detail : typeof detail === 'string' ? detail : err?.message
      setError(msg ?? 'Import failed — check your CSV format')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="p-8 max-w-2xl">
      <div className="mb-8">
        <div className="text-xs font-semibold tracking-widest text-blue-600 uppercase mb-1">
          Data ingestion
        </div>
        <h1 className="text-2xl font-bold text-gray-900">Import Bank Statement</h1>
        <p className="text-sm text-gray-500 mt-1">
          Upload a CSV from your bank. The AI pipeline will match transactions and flag exceptions automatically.
        </p>
      </div>

      {/* Format guide */}
      <div className="card mb-6 bg-blue-50 border-blue-200">
        <div className="text-xs font-semibold text-blue-700 mb-2">Expected CSV format</div>
        <div className="text-xs font-mono text-blue-900 bg-white border border-blue-200 rounded-lg p-3 overflow-x-auto">
          date,description,amount,reference<br />
          2024-10-01,ACH PAYROLL,-42350.00,PR-10-01<br />
          2024-10-03,SVC CHG MONTHLY,-35.00,SVC-1031<br />
          2024-10-05,STRIPE PAYOUT,18420.00,STR-2041
        </div>
        <p className="text-xs text-blue-600 mt-2">
          Flexible headers accepted: date/transaction_date, description/memo/narrative,
          amount or separate debit/credit columns, reference/ref (optional).
        </p>
      </div>

      <form onSubmit={handleSubmit} className="card space-y-5">
        {/* File picker */}
        <div>
          <label className="label">CSV File</label>
          <div
            onClick={() => fileRef.current?.click()}
            className={clsx(
              'border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors',
              file ? 'border-blue-400 bg-blue-50' : 'border-gray-300 hover:border-blue-400 hover:bg-gray-50'
            )}
          >
            <input
              ref={fileRef}
              type="file"
              accept=".csv"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0]
                if (f) { setFile(f); setError('') }
              }}
            />
            {file ? (
              <div>
                <div className="text-sm font-medium text-blue-700">{file.name}</div>
                <div className="text-xs text-blue-500 mt-1">
                  {(file.size / 1024).toFixed(1)} KB — click to change
                </div>
              </div>
            ) : (
              <div>
                <div className="text-sm text-gray-500">Click to select a CSV file</div>
                <div className="text-xs text-gray-400 mt-1">or drag and drop</div>
              </div>
            )}
          </div>
        </div>

        {/* Bank account */}
        <div>
          <label className="label">Bank Account ID</label>
          <input
            type="number"
            className="input"
            value={accountId}
            onChange={(e) => setAccountId(e.target.value)}
            min="1"
            placeholder="1"
          />
          <p className="text-xs text-gray-400 mt-1">
            Use the account ID from the Dashboard (account #1 = Operating Account)
          </p>
        </div>

        {/* Period */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="label">Period Start</label>
            <input
              type="date"
              className="input"
              value={periodStart}
              onChange={(e) => setPeriodStart(e.target.value)}
              required
            />
          </div>
          <div>
            <label className="label">Period End</label>
            <input
              type="date"
              className="input"
              value={periodEnd}
              onChange={(e) => setPeriodEnd(e.target.value)}
              required
            />
          </div>
        </div>

        {error && (
          <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
            {error}
          </div>
        )}

        <button type="submit" disabled={loading} className="btn-primary w-full">
          {loading ? 'Importing & running AI pipeline…' : 'Import & Reconcile'}
        </button>
      </form>

      {/* Result */}
      {result && (
        <div className="mt-6 card border-green-200 bg-green-50">
          <div className="flex items-center gap-2 mb-4">
            <span className="text-green-600 text-lg">✓</span>
            <span className="text-sm font-semibold text-green-800">Import complete</span>
          </div>
          <div className="space-y-2 text-sm">
            {[
              ['Account', result.account],
              ['Period', result.period],
              ['Rows imported', result.rows_imported],
              ['Rows skipped', result.rows_skipped],
              ['Matched', result.matched],
              ['Exceptions flagged', result.exceptions],
            ].map(([label, val]) => (
              <div key={String(label)} className="flex justify-between">
                <span className="text-gray-500">{label}</span>
                <span className="font-medium text-gray-900">{val}</span>
              </div>
            ))}
          </div>
          <div className="mt-4 flex gap-3">
            <button
              onClick={() => navigate('/app/exceptions')}
              className="btn-primary text-sm flex-1"
            >
              Review {result.exceptions} exception{result.exceptions !== 1 ? 's' : ''} →
            </button>
            <button
              onClick={() => navigate('/app/dashboard')}
              className="btn-secondary text-sm"
            >
              Dashboard
            </button>
          </div>
        </div>
      )}

      {/* Sample CSV download */}
      <div className="mt-6 text-center">
        <button
          onClick={() => {
            const csv = [
              'date,description,amount,reference',
              '2024-11-01,ACH PAYROLL,-42350.00,PR-11-01',
              '2024-11-03,SVC CHG MONTHLY,-35.00,SVC-1130',
              '2024-11-05,STRIPE PAYOUT,18420.00,STR-3001',
              '2024-11-08,AMAZON WEB SERVICES,-1247.33,AWS-NOV',
              '2024-11-10,WIRE IN - CLIENT A,75000.00,WR-CA-02',
              '2024-11-12,OFFICE LEASE NOV,-8500.00,LSE-NOV',
              '2024-11-15,GOOGLE WORKSPACE,-840.00,GWS-NOV',
              '2024-11-20,STRIPE PAYOUT,22100.00,STR-3002',
              '2024-11-28,UTILITY BILL NOV,-412.75,UTL-NOV',
              '2024-11-30,INTEREST CREDIT,127.50,INT-NOV',
            ].join('\n')
            const blob = new Blob([csv], { type: 'text/csv' })
            const url = URL.createObjectURL(blob)
            const a = document.createElement('a')
            a.href = url
            a.download = 'sample_bank_statement.csv'
            a.click()
          }}
          className="text-xs text-blue-600 hover:underline"
        >
          Download sample CSV to test with →
        </button>
      </div>
    </div>
  )
}
