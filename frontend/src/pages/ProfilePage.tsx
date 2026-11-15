import { useState } from 'react'
import { useAuth } from '../contexts/AuthContext'
import api from '../api/client'

export default function ProfilePage() {
  const { user, logout } = useAuth()
  const [fullName, setFullName] = useState(user?.full_name ?? '')
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [nameLoading, setNameLoading] = useState(false)
  const [pwLoading, setPwLoading] = useState(false)
  const [nameMsg, setNameMsg] = useState('')
  const [pwMsg, setPwMsg] = useState('')
  const [pwError, setPwError] = useState('')

  const saveName = async (e: React.FormEvent) => {
    e.preventDefault()
    setNameLoading(true)
    setNameMsg('')
    try {
      await api.patch('/users/me/profile', { full_name: fullName })
      setNameMsg('Name updated successfully')
    } catch {
      setNameMsg('Failed to update name')
    } finally {
      setNameLoading(false)
    }
  }

  const savePassword = async (e: React.FormEvent) => {
    e.preventDefault()
    setPwError('')
    setPwMsg('')
    if (newPassword !== confirmPassword) {
      setPwError('Passwords do not match')
      return
    }
    if (newPassword.length < 8) {
      setPwError('Password must be at least 8 characters')
      return
    }
    setPwLoading(true)
    try {
      await api.patch('/users/me/profile', {
        current_password: currentPassword,
        new_password: newPassword,
      })
      setPwMsg('Password changed successfully')
      setCurrentPassword('')
      setNewPassword('')
      setConfirmPassword('')
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setPwError(msg ?? 'Failed to change password')
    } finally {
      setPwLoading(false)
    }
  }

  return (
    <div className="p-8 max-w-lg">
      <div className="mb-8">
        <div className="text-xs font-semibold tracking-widest text-blue-600 uppercase mb-1">Account</div>
        <h1 className="text-2xl font-bold text-gray-900">Your Profile</h1>
      </div>

      {/* Account info */}
      <div className="card mb-5">
        <div className="flex items-center gap-4 mb-4">
          <div className="w-12 h-12 rounded-full bg-blue-100 flex items-center justify-center text-xl font-bold text-blue-700">
            {user?.full_name?.[0] ?? '?'}
          </div>
          <div>
            <div className="font-semibold text-gray-900">{user?.full_name}</div>
            <div className="text-sm text-gray-500">{user?.email}</div>
            <span className="inline-flex items-center mt-1 px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800 capitalize">
              {user?.role}
            </span>
          </div>
        </div>
      </div>

      {/* Change name */}
      <div className="card mb-5">
        <h2 className="text-sm font-semibold text-gray-900 mb-4">Display name</h2>
        <form onSubmit={saveName} className="space-y-3">
          <div>
            <label className="label">Full name</label>
            <input
              className="input"
              value={fullName}
              onChange={e => setFullName(e.target.value)}
              required
            />
          </div>
          {nameMsg && (
            <div className={`text-xs ${nameMsg.includes('success') ? 'text-green-600' : 'text-red-600'}`}>
              {nameMsg}
            </div>
          )}
          <button type="submit" disabled={nameLoading} className="btn-primary text-sm">
            {nameLoading ? 'Saving…' : 'Save name'}
          </button>
        </form>
      </div>

      {/* Change password */}
      <div className="card mb-5">
        <h2 className="text-sm font-semibold text-gray-900 mb-4">Change password</h2>
        <form onSubmit={savePassword} className="space-y-3">
          <div>
            <label className="label">Current password</label>
            <input
              type="password"
              className="input"
              value={currentPassword}
              onChange={e => setCurrentPassword(e.target.value)}
              required
            />
          </div>
          <div>
            <label className="label">New password</label>
            <input
              type="password"
              className="input"
              value={newPassword}
              onChange={e => setNewPassword(e.target.value)}
              required
            />
          </div>
          <div>
            <label className="label">Confirm new password</label>
            <input
              type="password"
              className="input"
              value={confirmPassword}
              onChange={e => setConfirmPassword(e.target.value)}
              required
            />
          </div>
          {pwError && <div className="text-xs text-red-600">{pwError}</div>}
          {pwMsg && <div className="text-xs text-green-600">{pwMsg}</div>}
          <button type="submit" disabled={pwLoading} className="btn-primary text-sm">
            {pwLoading ? 'Changing…' : 'Change password'}
          </button>
        </form>
      </div>

      {/* Sign out */}
      <button onClick={logout} className="btn-secondary text-sm w-full">
        Sign out
      </button>
    </div>
  )
}
