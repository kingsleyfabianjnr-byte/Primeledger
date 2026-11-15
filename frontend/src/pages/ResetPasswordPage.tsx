import { useState } from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import api from '../api/client'

export default function ResetPasswordPage() {
  const [params] = useSearchParams()
  const token = params.get('token') ?? ''
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [loading, setLoading] = useState(false)
  const [success, setSuccess] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (password !== confirm) { setError('Passwords do not match'); return }
    if (password.length < 8) { setError('Password must be at least 8 characters'); return }
    setLoading(true)
    setError('')
    try {
      await api.post('/users/reset-password', { token, new_password: password })
      setSuccess(true)
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(msg ?? 'Reset failed — the link may have expired. Request a new one.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold text-gray-900">Reset password</h1>
          <p className="text-sm text-gray-500 mt-1">Choose a new password for your account</p>
        </div>

        {success ? (
          <div className="card text-center">
            <div className="text-green-600 text-3xl mb-3">✓</div>
            <div className="text-sm font-semibold text-gray-900 mb-1">Password reset!</div>
            <div className="text-sm text-gray-500 mb-4">Your password has been updated. Sign in with your new password.</div>
            <Link to="/login" className="btn-primary w-full text-sm">Go to sign in →</Link>
          </div>
        ) : (
          <div className="card">
            {error && (
              <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">{error}</div>
            )}
            {!token && (
              <div className="mb-4 p-3 bg-amber-50 border border-amber-200 rounded-lg text-sm text-amber-700">
                Invalid link. <Link to="/forgot-password" className="underline">Request a new reset link</Link>
              </div>
            )}
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="label">New password</label>
                <input
                  type="password"
                  className="input"
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  required
                  autoFocus
                />
              </div>
              <div>
                <label className="label">Confirm new password</label>
                <input
                  type="password"
                  className="input"
                  value={confirm}
                  onChange={e => setConfirm(e.target.value)}
                  required
                />
              </div>
              <button type="submit" disabled={loading || !token} className="btn-primary w-full">
                {loading ? 'Resetting…' : 'Reset password'}
              </button>
            </form>
            <div className="mt-4 text-center">
              <Link to="/login" className="text-xs text-gray-500 hover:text-gray-900">← Back to sign in</Link>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
