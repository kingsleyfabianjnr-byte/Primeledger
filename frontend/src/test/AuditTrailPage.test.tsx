import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import AuditTrailPage from '../pages/AuditTrailPage'

vi.mock('../api/client', () => ({
  auditApi: {
    list: vi.fn().mockResolvedValue({
      data: [
        {
          id: 1,
          reconciliation_id: 1,
          user_id: null,
          action: 'match_created',
          entity_type: 'bank_transaction',
          entity_id: 1,
          details: { method: 'exact', confidence: 0.98 },
          previous_hash: null,
          entry_hash: 'abc123def456abc123def456abc123def456abc123def456abc123def456abc1',
          created_at: '2024-11-01T08:01:00Z',
        },
        {
          id: 2,
          reconciliation_id: 1,
          user_id: 2,
          action: 'entry_approved',
          entity_type: 'exception',
          entity_id: 1,
          details: { exception_number: 1 },
          previous_hash: 'abc123def456abc123def456abc123def456abc123def456abc123def456abc1',
          entry_hash: 'def456abc123def456abc123def456abc123def456abc123def456abc123def4',
          created_at: '2024-11-01T10:30:00Z',
        },
      ],
    }),
  },
  default: { interceptors: { request: { use: vi.fn() }, response: { use: vi.fn() } } },
}))

describe('AuditTrailPage', () => {
  it('renders the page title', async () => {
    render(<MemoryRouter><AuditTrailPage /></MemoryRouter>)
    expect(await screen.findByText('Audit Trail')).toBeInTheDocument()
  })

  it('shows audit log entries', async () => {
    render(<MemoryRouter><AuditTrailPage /></MemoryRouter>)
    // Both "Match created" and "Entry approved" appear in the legend + the table rows
    const matchCreatedEls = await screen.findAllByText('Match created')
    expect(matchCreatedEls.length).toBeGreaterThanOrEqual(1)
    const entryApprovedEls = await screen.findAllByText('Entry approved')
    expect(entryApprovedEls.length).toBeGreaterThanOrEqual(1)
  })

  it('shows genesis for the first entry', async () => {
    render(<MemoryRouter><AuditTrailPage /></MemoryRouter>)
    expect(await screen.findByText('genesis')).toBeInTheDocument()
  })

  it('shows chained for entries with previous hash', async () => {
    render(<MemoryRouter><AuditTrailPage /></MemoryRouter>)
    expect(await screen.findByText('✓ chained')).toBeInTheDocument()
  })

  it('shows AI agent label for entries with no user', async () => {
    render(<MemoryRouter><AuditTrailPage /></MemoryRouter>)
    expect(await screen.findByText('AI agent')).toBeInTheDocument()
  })
})
