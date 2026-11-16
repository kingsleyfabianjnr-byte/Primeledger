import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import LoginPage from '../pages/LoginPage'
import { AuthProvider } from '../contexts/AuthContext'

// Mock the API
vi.mock('../api/client', () => ({
  authApi: {
    login: vi.fn(),
    me: vi.fn(),
  },
  default: { interceptors: { request: { use: vi.fn() }, response: { use: vi.fn() } } },
}))

const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

import { authApi } from '../api/client'

describe('LoginPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    if (typeof localStorage !== 'undefined' && localStorage.clear) {
      localStorage.clear()
    }
  })

  it('renders login form with empty fields and demo role buttons', () => {
    ;(authApi.me as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('no token'))
    render(
      <MemoryRouter>
        <AuthProvider>
          <LoginPage />
        </AuthProvider>
      </MemoryRouter>
    )
    // heading
    expect(screen.getByRole('heading', { name: /Sign in/i })).toBeInTheDocument()
    // fields start empty
    const emailInput = screen.getByLabelText(/Email/i) as HTMLInputElement
    const passwordInput = screen.getByLabelText(/Password/i) as HTMLInputElement
    expect(emailInput.value).toBe('')
    expect(passwordInput.value).toBe('')
    // demo role buttons present
    expect(screen.getByRole('button', { name: /preparer/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /approver/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /admin/i })).toBeInTheDocument()
  })

  it('fills credentials when a demo role button is clicked', () => {
    ;(authApi.me as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('no token'))
    render(
      <MemoryRouter>
        <AuthProvider>
          <LoginPage />
        </AuthProvider>
      </MemoryRouter>
    )
    fireEvent.click(screen.getByRole('button', { name: /preparer/i }))
    const emailInput = screen.getByLabelText(/Email/i) as HTMLInputElement
    expect(emailInput.value).toBe('demo@primeledger.ai')
  })

  it('shows error on wrong credentials', async () => {
    ;(authApi.me as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('no token'))
    ;(authApi.login as ReturnType<typeof vi.fn>).mockRejectedValue({
      response: { status: 401 },
    })

    render(
      <MemoryRouter>
        <AuthProvider>
          <LoginPage />
        </AuthProvider>
      </MemoryRouter>
    )

    fireEvent.change(screen.getByLabelText(/Email/i), {
      target: { value: 'wrong@test.com' },
    })
    fireEvent.change(screen.getByLabelText(/Password/i), {
      target: { value: 'wrongpass' },
    })
    fireEvent.submit(screen.getByRole('button', { name: /^Sign in$/i }))

    await waitFor(() => {
      expect(screen.getByText(/Incorrect email or password/i)).toBeInTheDocument()
    })
  })
})
