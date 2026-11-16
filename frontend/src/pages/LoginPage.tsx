import { useState, FormEvent } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'

export default function LoginPage() {
  const { login, user } = useAuth()
  const navigate = useNavigate()
  // Start EMPTY — user types their own credentials
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  if (user) {
    navigate('/app/dashboard', { replace: true })
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(email, password)
      navigate('/app/dashboard', { replace: true })
    } catch {
      setError('Incorrect email or password.')
    } finally {
      setLoading(false)
    }
  }

  // Fill in demo credentials with one click
  const fillDemo = (role: 'preparer' | 'approver' | 'admin') => {
    const creds = {
      preparer: { email: 'demo@primeledger.ai',     password: 'demo1234'    },
      approver: { email: 'approver@primeledger.ai', password: 'approver123' },
      admin:    { email: 'admin@primeledger.ai',    password: 'admin123'    },
    }
    setEmail(creds[role].email)
    setPassword(creds[role].password)
    setError('')
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <div className="w-full max-w-sm">

        {/* Logo + heading */}
        <div className="text-center mb-8">
          <Link to="/" className="inline-flex items-center gap-2 justify-center mb-6">
            <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center">
              <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M9 7h6m0 10v-3m-3 3h.01M9 17h.01M9 11h.01M12 11h.01M15 11h.01M4 19h16a2 2 0 002-2V7a2 2 0 00-2-2H4a2 2 0 00-2 2v10a2 2 0 002 2z" />
              </svg>
            </div>
            <span className="font-semibold text-gray-900 text-lg">PrimeLedger</span>
          </Link>
          <h1 className="text-2xl font-bold text-gray-900 mb-1">Sign in</h1>
          <p className="text-sm text-gray-500">Access your reconciliation workspace</p>
        </div>

        {/* Login form */}
        <div className="card shadow-sm">
          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="login-email" className="label">Email</label>
              <input
                id="login-email"
                type="email"
                className="input"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoFocus
                placeholder="you@company.com"
              />
            </div>
            <div>
              <label htmlFor="login-password" className="label">Password</label>
              <input
                id="login-password"
                type="password"
                className="input"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                placeholder="••••••••"
              />
            </div>
            <button type="submit" disabled={loading} className="btn-primary w-full mt-2">
              {loading ? 'Signing in…' : 'Sign in'}
            </button>
            <div className="text-center">
              <Link to="/forgot-password" className="text-xs text-gray-500 hover:text-blue-600 transition-colors">
                Forgot your password?
              </Link>
            </div>
          </form>
        </div>

        {/* Demo credentials — clickable to fill the form */}
        <div className="mt-5 p-4 bg-blue-50 border border-blue-200 rounded-xl text-xs text-blue-800">
          <div className="font-semibold mb-2">Try the demo — click a role to fill in credentials:</div>
          <div className="flex gap-2 flex-wrap">
            {(['preparer', 'approver', 'admin'] as const).map(role => (
              <button
                key={role}
                type="button"
                onClick={() => fillDemo(role)}
                className="px-3 py-1.5 bg-white border border-blue-200 rounded-lg text-xs font-medium text-blue-700 hover:bg-blue-100 transition-colors capitalize"
              >
                {role}
              </button>
            ))}
          </div>
          <p className="mt-2 text-blue-600 text-xs">Click a role above, then click Sign in.</p>
        </div>

        {/* Sign up link */}
        <div className="mt-4 text-center text-xs text-gray-500">
          Don't have an account?{' '}
          <span className="text-gray-700 font-medium">Ask your admin to invite you.</span>
        </div>
      </div>
    </div>
  )
}
