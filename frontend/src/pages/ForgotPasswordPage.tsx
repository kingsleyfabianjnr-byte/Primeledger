import { useState } from 'react'
import { Link } from 'react-router-dom'
import api from '../api/client'

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [sent, setSent] = useState(false)
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    try {
      await api.post('/users/forgot-password', { email })
    } finally {
      setSent(true) // always show success — don't reveal if email exists
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold text-gray-900">Forgot password?</h1>
          <p className="text-sm text-gray-500 mt-1">Enter your email and we'll send a reset link</p>
        </div>

        {sent ? (
          <div className="card text-center">
            <div className="text-blue-600 text-3xl mb-3">✉</div>
            <div className="text-sm font-semibold text-gray-900 mb-1">Check your email</div>
            <div className="text-sm text-gray-500 mb-4">
              If <strong>{email}</strong> is registered, a reset link is on its way. Check your spam folder too.
            </div>
            <Link to="/login" className="btn-secondary w-full text-sm">Back to sign in</Link>
          </div>
        ) : (
          <div className="card">
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="label">Email address</label>
                <input
                  type="email"
                  className="input"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  required
                  autoFocus
                  placeholder="you@company.com"
                />
              </div>
              <button type="submit" disabled={loading} className="btn-primary w-full">
                {loading ? 'Sending…' : 'Send reset link'}
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
