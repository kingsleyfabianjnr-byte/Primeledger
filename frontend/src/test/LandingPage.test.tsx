import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import LandingPage from '../pages/LandingPage'

describe('LandingPage', () => {
  it('renders the hero headline', () => {
    render(<MemoryRouter><LandingPage /></MemoryRouter>)
    expect(screen.getByText(/Close the month in minutes/i)).toBeInTheDocument()
  })

  it('shows the four agent steps', () => {
    render(<MemoryRouter><LandingPage /></MemoryRouter>)
    expect(screen.getByText('Ingest')).toBeInTheDocument()
    expect(screen.getByText('Match')).toBeInTheDocument()
    expect(screen.getByText('Investigate')).toBeInTheDocument()
    expect(screen.getByText('Resolve')).toBeInTheDocument()
  })

  it('renders the IBM watsonx section', () => {
    render(<MemoryRouter><LandingPage /></MemoryRouter>)
    expect(screen.getByText(/Built with IBM watsonx/i)).toBeInTheDocument()
  })

  it('has a "Try the demo" CTA linking to /login', () => {
    render(<MemoryRouter><LandingPage /></MemoryRouter>)
    const links = screen.getAllByRole('link', { name: /Try the demo/i })
    expect(links.length).toBeGreaterThan(0)
    expect(links[0]).toHaveAttribute('href', '/login')
  })

  it('shows the exception card preview with AI confidence', () => {
    render(<MemoryRouter><LandingPage /></MemoryRouter>)
    expect(screen.getByText('Confidence 0.94')).toBeInTheDocument()
    expect(screen.getByText('No matching entry')).toBeInTheDocument()
  })
})
