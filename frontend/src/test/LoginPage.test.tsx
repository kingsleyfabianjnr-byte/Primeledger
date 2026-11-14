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
    // localStorage may not be available in all jsdom environments
    if (typeof localStorage !== 'undefined' && localStorage.clear) {
      localStorage.clear()
    }
  })

  it('renders login form with pre-filled demo credentials', () => {
    ;(authApi.me as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('no token'))
    render(
      <MemoryRouter>
        <AuthProvider>
          <LoginPage />
        </AuthProvider>
      </MemoryRouter>
    )
    // h1 heading (there's also a button with "Sign in")
    expect(screen.getByRole('heading', { name: /Sign in/i })).toBeInTheDocument()
    expect(screen.getByDisplayValue('demo@primeledger.ai')).toBeInTheDocument()
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
    fireEvent.submit(screen.getByRole('button', { name: /Sign in/i }))

    await waitFor(() => {
      expect(screen.getByText(/Invalid email or password/i)).toBeInTheDocument()
    })
  })
})
