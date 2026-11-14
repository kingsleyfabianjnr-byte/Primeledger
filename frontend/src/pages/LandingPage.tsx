import { Link } from 'react-router-dom'

export default function LandingPage() {
  return (
    <div className="bg-white min-h-screen font-sans">
      {/* NAV */}
      <header className="border-b border-gray-100 sticky top-0 bg-white z-10">
        <div className="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 bg-blue-600 rounded-md flex items-center justify-center">
              <svg className="w-3.5 h-3.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M9 7h6m0 10v-3m-3 3h.01M9 17h.01M9 11h.01M12 11h.01M15 11h.01M4 19h16a2 2 0 002-2V7a2 2 0 00-2-2H4a2 2 0 00-2 2v10a2 2 0 002 2z" />
              </svg>
            </div>
            <span className="font-semibold text-gray-900">PrimeLedger</span>
          </div>
          <nav className="hidden md:flex items-center gap-8 text-sm text-gray-600">
            <a href="#how-it-works" className="hover:text-gray-900 transition-colors">How it works</a>
            <a href="#controls" className="hover:text-gray-900 transition-colors">Controls</a>
            <a href="#who-its-for" className="hover:text-gray-900 transition-colors">Who it's for</a>
          </nav>
          <Link to="/login" className="btn-primary text-xs px-4 py-2">Try the demo</Link>
        </div>
      </header>

      {/* HERO */}
      <section className="max-w-6xl mx-auto px-6 pt-20 pb-24 grid md:grid-cols-2 gap-12 items-center">
        <div>
          <div className="text-xs font-semibold tracking-widest text-blue-600 uppercase mb-4">
            Agentic Bank Reconciliation
          </div>
          <h1 className="text-4xl md:text-5xl font-bold text-gray-900 leading-tight mb-5">
            Close the month in minutes, not days.
          </h1>
          <p className="text-gray-500 text-base leading-relaxed mb-8 max-w-md">
            PrimeLedger's AI agents match every bank transaction to your ledger,
            explain every exception in plain language, and draft the fix.
            Your accountants review and approve. Nothing posts without them.
          </p>
          <div className="flex items-center gap-3">
            <Link to="/login" className="btn-primary">Try the demo</Link>
            <a href="#how-it-works" className="btn-secondary">See how it works</a>
          </div>
        </div>

        {/* Exception card preview */}
        <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
          <div className="bg-gray-50 border-b border-gray-200 px-5 py-3 flex items-center justify-between">
            <span className="text-sm font-medium text-gray-900">Exception 3 of 7 · Operating account</span>
            <span className="text-xs text-gray-400">Oct 2024</span>
          </div>
          <div className="p-5 space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <div className="text-xs text-gray-400 uppercase tracking-wide mb-1">Bank statement</div>
                <div className="text-sm font-medium text-gray-900">Oct 31 · –$35.00</div>
                <div className="text-xs text-gray-500">SVC CHG MONTHLY</div>
              </div>
              <div>
                <div className="text-xs text-gray-400 uppercase tracking-wide mb-1">General ledger</div>
                <div className="text-sm font-medium text-red-500">No matching entry</div>
              </div>
            </div>

            {/* Confidence badge */}
            <div className="flex items-center gap-2 bg-green-50 border border-green-200 rounded-lg px-3 py-2">
              <span className="text-xs font-semibold text-green-700 bg-green-100 rounded px-1.5 py-0.5">AI</span>
              <span className="text-xs font-medium text-green-800">Confidence 0.94</span>
            </div>

            <p className="text-xs text-gray-600 leading-relaxed">
              The bank charged its monthly service fee on Oct 31. It was never recorded in the ledger.
              Same amount and description as the previous three months.
            </p>

            {/* Suggested journal entry */}
            <div className="bg-gray-50 rounded-lg p-3 text-xs font-mono text-gray-700 space-y-1">
              <div>Dr 6200 Bank Fees ......... 35.00</div>
              <div>Cr 1010 Operating Cash ... 35.00</div>
            </div>

            {/* Actions */}
            <div className="flex items-center gap-2 pt-1">
              <button className="btn-primary text-xs px-4 py-1.5">Approve</button>
              <button className="btn-secondary text-xs px-4 py-1.5">Edit</button>
              <button className="btn-ghost text-xs px-3 py-1.5 text-red-600 hover:bg-red-50">Reject</button>
            </div>
          </div>
        </div>
      </section>

      {/* THE PROBLEM */}
      <section className="bg-gray-50 py-20 border-t border-gray-100">
        <div className="max-w-6xl mx-auto px-6">
          <div className="text-xs font-semibold tracking-widest text-blue-600 uppercase mb-3">The problem</div>
          <h2 className="text-3xl font-bold text-gray-900 mb-12">
            Month-end still runs on spreadsheets<br className="hidden md:block" /> and detective work.
          </h2>
          <div className="grid md:grid-cols-3 gap-6">
            {[
              {
                title: 'Days of manual matching',
                desc: 'Accountants line up statement rows against ledger entries by hand, every account, every month.',
              },
              {
                title: 'Rules break on real data',
                desc: 'Truncated descriptions, split payments and netted fees defeat exact-match rules, so exceptions pile up.',
              },
              {
                title: 'Gaps become audit findings',
                desc: 'Sampled reviews and undocumented fixes leave auditors without the evidence they need.',
              },
            ].map((item) => (
              <div key={item.title} className="card">
                <h3 className="text-sm font-semibold text-gray-900 mb-2">{item.title}</h3>
                <p className="text-sm text-gray-500 leading-relaxed">{item.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* HOW IT WORKS */}
      <section id="how-it-works" className="py-20">
        <div className="max-w-6xl mx-auto px-6">
          <div className="text-xs font-semibold tracking-widest text-blue-600 uppercase mb-3">How it works</div>
          <h2 className="text-3xl font-bold text-gray-900 mb-3">Four agents. One reconciled month.</h2>
          <p className="text-gray-500 mb-12 text-sm">
            Exact matches are made by code. The agents take on what's left: the messy cases a rule can't handle.
          </p>
          <div className="grid md:grid-cols-4 gap-5">
            {[
              {
                num: '01',
                title: 'Ingest',
                desc: 'Reads your bank statement and ledger export, then cleans dates, amounts, signs and payee names.',
              },
              {
                num: '02',
                title: 'Match',
                desc: 'Pairs transactions exactly, fuzzily, and across splits and batches, with a confidence score on every match.',
              },
              {
                num: '03',
                title: 'Investigate',
                desc: "Explains why each leftover item didn't match: timing, fees, duplicates, FX or a missing entry.",
              },
              {
                num: '04',
                title: 'Resolve',
                desc: 'Drafts the adjusting journal entry and sends it to your approver. Approve, edit or reject in one click.',
              },
            ].map((step) => (
              <div key={step.num} className="card">
                <div className="text-xs font-bold text-blue-500 mb-3">{step.num}</div>
                <h3 className="text-sm font-semibold text-gray-900 mb-2">{step.title}</h3>
                <p className="text-xs text-gray-500 leading-relaxed">{step.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* TRUST AND CONTROLS */}
      <section id="controls" className="bg-gray-50 py-20 border-t border-gray-100">
        <div className="max-w-6xl mx-auto px-6">
          <div className="text-xs font-semibold tracking-widest text-blue-600 uppercase mb-3">Trust and controls</div>
          <h2 className="text-3xl font-bold text-gray-900 mb-3">The agents propose. Your people decide.</h2>
          <p className="text-gray-500 text-sm mb-12 max-w-lg">
            Built for finance teams that answer to auditors. Every control is enforced by the system, not by policy.
          </p>
          <div className="grid md:grid-cols-3 gap-x-8 gap-y-8">
            {[
              {
                title: 'Human approval on every entry',
                desc: 'Agents can only create pending entries. Only a named approver can post one.',
              },
              {
                title: 'Confidence you can see',
                desc: 'Every match carries a score. Anything below your threshold goes to a person.',
              },
              {
                title: 'Segregation of duties',
                desc: "Whoever prepares or edits an entry can't approve it. The system blocks it.",
              },
              {
                title: 'Every decision explained',
                desc: 'Each match and exception keeps its reasoning and the source rows behind it.',
              },
              {
                title: 'Tamper-evident audit trail',
                desc: 'A hash-linked log of every action by every person and agent, ready to export.',
              },
              {
                title: 'Data kept private',
                desc: 'Account numbers are masked before any text reaches the AI model.',
              },
            ].map((ctrl) => (
              <div key={ctrl.title}>
                <h3 className="text-sm font-semibold text-gray-900 mb-1">{ctrl.title}</h3>
                <p className="text-sm text-gray-500 leading-relaxed">{ctrl.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* WHO IT'S FOR */}
      <section id="who-its-for" className="py-20">
        <div className="max-w-6xl mx-auto px-6">
          <div className="text-xs font-semibold tracking-widest text-blue-600 uppercase mb-3">Who it's for</div>
          <h2 className="text-3xl font-bold text-gray-900 mb-12">For the teams that own the close.</h2>
          <div className="grid md:grid-cols-3 gap-6">
            {[
              {
                title: 'Controllers and accounting teams',
                desc: 'At mid-size companies that close many bank accounts every month.',
              },
              {
                title: 'Community banks and credit unions',
                desc: 'That need complete, documented reconciliations for examiners.',
              },
              {
                title: 'Bookkeeping and outsourced accounting firms',
                desc: 'Managing many client ledgers with a small team.',
              },
            ].map((item) => (
              <div key={item.title} className="card">
                <h3 className="text-sm font-semibold text-gray-900 mb-2">{item.title}</h3>
                <p className="text-sm text-gray-500 leading-relaxed">{item.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* UNDER THE HOOD */}
      <section className="py-20 border-t border-gray-100">
        <div className="max-w-6xl mx-auto px-6 grid md:grid-cols-2 gap-12 items-center">
          <div>
            <div className="text-xs font-semibold tracking-widest text-blue-600 uppercase mb-3">Under the hood</div>
            <h2 className="text-3xl font-bold text-gray-900 mb-4">Built with IBM watsonx.</h2>
            <p className="text-gray-500 text-sm leading-relaxed">
              Agents run on watsonx Orchestrate. Reasoning and explanations come from an IBM Granite model on watsonx.ai.
              Matching that rules can do, code does first.
            </p>
          </div>
          <div className="space-y-3">
            {[
              { label: 'Agents', value: 'watsonx Orchestrate' },
              { label: 'Model', value: 'IBM Granite on watsonx.ai' },
              { label: 'App', value: 'React, FastAPI, PostgreSQL' },
              { label: 'Built with', value: 'IBM Bob' },
            ].map((row) => (
              <div key={row.label} className="flex items-center justify-between py-3 border-b border-gray-100">
                <span className="text-sm text-gray-500">{row.label}</span>
                <span className="text-sm font-medium text-gray-900">{row.value}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="bg-gray-900 py-20">
        <div className="max-w-6xl mx-auto px-6 flex flex-col md:flex-row items-center justify-between gap-6">
          <div>
            <h2 className="text-2xl font-bold text-white mb-2">See a month reconcile itself.</h2>
            <p className="text-gray-400 text-sm">Run the demo on a sample month and approve the fixes yourself.</p>
          </div>
          <Link to="/login" className="btn-secondary shrink-0">Try the demo</Link>
        </div>
      </section>

      {/* FOOTER */}
      <footer className="border-t border-gray-100 py-8">
        <div className="max-w-6xl mx-auto px-6 flex flex-col md:flex-row items-center justify-between gap-4 text-xs text-gray-400">
          <span>PrimeLedger by Spine Technologies</span>
          <span>Built for the IBM SkillsBuild AI Experiential Learning Lab · Prototype using synthetic data</span>
        </div>
      </footer>
    </div>
  )
}
