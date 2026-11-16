import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import DashboardPage from '../pages/DashboardPage'
import { AuthProvider } from '../contexts/AuthContext'

vi.mock('../api/client', () => {
  const stats = {
    total_accounts: 3,
    active_reconciliations: 2,
    exceptions_open: 7,
    matches_this_month: 7,
    match_rate: 50.0,
    reconciliations: [
      {
        id: 1,
        bank_account_id: 1,
        period_start: '2024-10-01',
        period_end: '2024-10-31',
        status: 'in_progress',
        total_transactions: 14,
        matched_count: 7,
        exception_count: 7,
        bank_balance: '67054.42',
        ledger_balance: '66926.92',
        created_at: '2024-10-01T00:00:00Z',
        completed_at: null,
        bank_account: {
          id: 1,
          name: 'Operating Account',
          account_number: '1000234567',
          masked_number: '****4567',
          entity_name: 'PrimeLedger Inc.',
          currency: 'USD',
          is_active: true,
          created_at: '2024-01-01T00:00:00Z',
        },
      },
    ],
  }
  return {
    authApi: { me: vi.fn().mockRejectedValue(new Error('no token')) },
    dashboardApi: { get: vi.fn().mockResolvedValue({ data: stats }) },
    reconciliationsApi: { create: vi.fn().mockResolvedValue({ data: {} }) },
    contractsApi: { list: vi.fn().mockResolvedValue({ data: [] }) },
    default: { interceptors: { request: { use: vi.fn() }, response: { use: vi.fn() } } },
  }
})

const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return { ...actual, useNavigate: () => mockNavigate }
})

function Wrapper({ children }: { children: React.ReactNode }) {
  return (
    <MemoryRouter>
      <AuthProvider>{children}</AuthProvider>
    </MemoryRouter>
  )
}

describe('DashboardPage', () => {
  it('renders the dashboard heading', async () => {
    render(<Wrapper><DashboardPage /></Wrapper>)
    expect(await screen.findByRole('heading', { name: /Dashboard/i })).toBeInTheDocument()
  })

  it('shows stat cards with correct values', async () => {
    render(<Wrapper><DashboardPage /></Wrapper>)
    expect(await screen.findByText('3')).toBeInTheDocument() // total accounts
    expect(await screen.findByText('50%')).toBeInTheDocument() // match rate
  })

  it('shows the reconciliation table', async () => {
    render(<Wrapper><DashboardPage /></Wrapper>)
    expect(await screen.findByText('Operating Account')).toBeInTheDocument()
    expect(await screen.findByText('****4567')).toBeInTheDocument()
  })

  it('opens new reconciliation modal on button click', async () => {
    render(<Wrapper><DashboardPage /></Wrapper>)
    const btn = await screen.findByRole('button', { name: /New reconciliation/i })
    fireEvent.click(btn)
    expect(await screen.findByText('Start new reconciliation')).toBeInTheDocument()
  })

  it('shows dynamic period label for active reconciliation', async () => {
    render(<Wrapper><DashboardPage /></Wrapper>)
    // "October 2024" should appear in header and/or table rows
    const els = await screen.findAllByText(/October 2024/i)
    expect(els.length).toBeGreaterThanOrEqual(1)
  })
})
