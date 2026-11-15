import { useEffect, useState } from 'react'
import { useAuth } from '../contexts/AuthContext'
import { User } from '../api/client'
import api from '../api/client'
import clsx from 'clsx'

const ROLE_COLORS: Record<string, string> = {
  admin: 'bg-purple-100 text-purple-800',
  approver: 'bg-green-100 text-green-800',
  preparer: 'bg-blue-100 text-blue-800',
  viewer: 'bg-gray-100 text-gray-700',
}

type InviteForm = { email: string; full_name: string; role: string }

export default function UsersPage() {
  const { user: me } = useAuth()
  const [users, setUsers] = useState<User[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [showInvite, setShowInvite] = useState(false)
  const [inviteForm, setInviteForm] = useState<InviteForm>({ email: '', full_name: '', role: 'preparer' })
  const [inviteLoading, setInviteLoading] = useState(false)
  const [inviteSuccess, setInviteSuccess] = useState('')
  const [inviteError, setInviteError] = useState('')

  const fetchUsers = () =>
    api.get<User[]>('/users')
      .then(r => setUsers(r.data))
      .catch(() => setError('Failed to load users'))
      .finally(() => setLoading(false))

  useEffect(() => { fetchUsers() }, [])

  const handleInvite = async (e: React.FormEvent) => {
    e.preventDefault()
    setInviteLoading(true)
    setInviteError('')
    setInviteSuccess('')
    try {
      await api.post('/users/invite', inviteForm)
      setInviteSuccess(`Invite sent to ${inviteForm.email}`)
      setInviteForm({ email: '', full_name: '', role: 'preparer' })
      fetchUsers()
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setInviteError(msg ?? 'Invite failed')
    } finally {
      setInviteLoading(false)
    }
  }

  const toggleActive = async (u: User) => {
    await api.patch(`/users/${u.id}`, { is_active: !u.is_active })
    setUsers(prev => prev.map(x => x.id === u.id ? { ...x, is_active: !u.is_active } : x))
  }

  const changeRole = async (u: User, role: string) => {
    await api.patch(`/users/${u.id}`, { role })
    setUsers(prev => prev.map(x => x.id === u.id ? { ...x, role: role as User['role'] } : x))
  }

  if (me?.role !== 'admin') {
    return <div className="p-8 text-sm text-red-600">Admin access required.</div>
  }

  return (
    <div className="p-8 max-w-5xl">
      <div className="mb-6 flex items-start justify-between">
        <div>
          <div className="text-xs font-semibold tracking-widest text-blue-600 uppercase mb-1">Admin</div>
          <h1 className="text-2xl font-bold text-gray-900">User Management</h1>
          <p className="text-sm text-gray-500 mt-1">{users.length} users · only admins can manage access</p>
        </div>
        <button onClick={() => setShowInvite(!showInvite)} className="btn-primary text-sm">
          + Invite user
        </button>
      </div>

      {/* Invite form */}
      {showInvite && (
        <div className="card mb-6 border-blue-200 bg-blue-50">
          <h2 className="text-sm font-semibold text-gray-900 mb-4">Invite a new user</h2>
          {inviteSuccess && (
            <div className="mb-3 p-3 bg-green-50 border border-green-200 rounded-lg text-sm text-green-700">
              ✓ {inviteSuccess}
            </div>
          )}
          {inviteError && (
            <div className="mb-3 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
              {inviteError}
            </div>
          )}
          <form onSubmit={handleInvite} className="grid md:grid-cols-3 gap-4">
            <div>
              <label className="label">Full name</label>
              <input
                className="input"
                value={inviteForm.full_name}
                onChange={e => setInviteForm(f => ({ ...f, full_name: e.target.value }))}
                required
                placeholder="Jane Smith"
              />
            </div>
            <div>
              <label className="label">Email</label>
              <input
                type="email"
                className="input"
                value={inviteForm.email}
                onChange={e => setInviteForm(f => ({ ...f, email: e.target.value }))}
                required
                placeholder="jane@company.com"
              />
            </div>
            <div>
              <label className="label">Role</label>
              <select
                className="input"
                value={inviteForm.role}
                onChange={e => setInviteForm(f => ({ ...f, role: e.target.value }))}
              >
                <option value="preparer">Preparer</option>
                <option value="approver">Approver</option>
                <option value="viewer">Viewer</option>
                <option value="admin">Admin</option>
              </select>
            </div>
            <div className="md:col-span-3 flex gap-3">
              <button type="submit" disabled={inviteLoading} className="btn-primary text-sm">
                {inviteLoading ? 'Sending invite…' : 'Send invite email'}
              </button>
              <button type="button" onClick={() => setShowInvite(false)} className="btn-secondary text-sm">
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Users table */}
      {loading ? (
        <div className="text-sm text-gray-400 py-8 text-center">Loading users…</div>
      ) : error ? (
        <div className="text-sm text-red-600">{error}</div>
      ) : (
        <div className="card p-0 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-100">
                <th className="text-left text-xs font-medium text-gray-500 px-5 py-3">Name</th>
                <th className="text-left text-xs font-medium text-gray-500 px-5 py-3">Email</th>
                <th className="text-left text-xs font-medium text-gray-500 px-5 py-3">Role</th>
                <th className="text-left text-xs font-medium text-gray-500 px-5 py-3">Status</th>
                <th className="text-left text-xs font-medium text-gray-500 px-5 py-3">Joined</th>
                <th className="text-left text-xs font-medium text-gray-500 px-5 py-3">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {users.map(u => (
                <tr key={u.id} className={clsx('hover:bg-gray-50 transition-colors', !u.is_active && 'opacity-50')}>
                  <td className="px-5 py-3.5 font-medium text-gray-900">
                    {u.full_name}
                    {u.id === me?.id && <span className="ml-1.5 text-xs text-blue-500">(you)</span>}
                  </td>
                  <td className="px-5 py-3.5 text-gray-600 text-xs">{u.email}</td>
                  <td className="px-5 py-3.5">
                    {u.id === me?.id ? (
                      <span className={clsx('inline-flex items-center px-2 py-0.5 rounded text-xs font-medium', ROLE_COLORS[u.role])}>
                        {u.role}
                      </span>
                    ) : (
                      <select
                        className="text-xs border border-gray-200 rounded px-2 py-1"
                        value={u.role}
                        onChange={e => changeRole(u, e.target.value)}
                      >
                        <option value="preparer">Preparer</option>
                        <option value="approver">Approver</option>
                        <option value="viewer">Viewer</option>
                        <option value="admin">Admin</option>
                      </select>
                    )}
                  </td>
                  <td className="px-5 py-3.5">
                    <span className={clsx(
                      'inline-flex items-center px-2 py-0.5 rounded text-xs font-medium',
                      u.is_active ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-500'
                    )}>
                      {u.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td className="px-5 py-3.5 text-xs text-gray-500">
                    {new Date(u.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
                  </td>
                  <td className="px-5 py-3.5">
                    {u.id !== me?.id && (
                      <button
                        onClick={() => toggleActive(u)}
                        className={clsx(
                          'text-xs font-medium transition-colors',
                          u.is_active
                            ? 'text-red-600 hover:text-red-800'
                            : 'text-green-600 hover:text-green-800'
                        )}
                      >
                        {u.is_active ? 'Deactivate' : 'Reactivate'}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Role legend */}
      <div className="mt-6 p-4 bg-gray-50 border border-gray-200 rounded-xl">
        <div className="text-xs font-semibold text-gray-700 mb-2">Role permissions</div>
        <div className="grid md:grid-cols-4 gap-3 text-xs text-gray-500">
          <div><span className="font-medium text-gray-700">Preparer</span> — uploads data, reviews exceptions, cannot approve</div>
          <div><span className="font-medium text-gray-700">Approver</span> — can approve and reject journal entries</div>
          <div><span className="font-medium text-gray-700">Viewer</span> — read-only, can download exports</div>
          <div><span className="font-medium text-gray-700">Admin</span> — full access including user management</div>
        </div>
      </div>
    </div>
  )
}
