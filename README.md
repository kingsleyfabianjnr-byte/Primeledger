# PrimeLedger

**Agentic Bank Reconciliation** — AI agents match every bank transaction to your ledger, explain every exception in plain language, and draft the fix. Your accountants review and approve. Nothing posts without them.

## Stack
- **Frontend**: React 18 + Vite + React Router + TailwindCSS
- **Backend**: FastAPI + SQLAlchemy + PostgreSQL (dev: SQLite)
- **AI Pipeline**: IBM watsonx Orchestrate (mocked in dev)
- **Auth**: JWT (FastAPI Users)

## Screens
1. **Landing Page** — public marketing page
2. **Dashboard** — reconciliation overview per entity/month
3. **Exception Queue** — AI-identified items needing human review
4. **Audit Trail** — tamper-evident log of every action

## Quick Start

### Backend
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

### Full stack (Docker)
```bash
docker-compose up
```

## Architecture

```
frontend/           # React SPA
  src/
    pages/          # Landing, Dashboard, ExceptionQueue, AuditTrail, Login
    components/     # Shared UI components
    hooks/          # Custom React hooks
    api/            # Axios client + typed API calls

backend/            # FastAPI application
  app/
    api/            # Route handlers
    models/         # SQLAlchemy ORM models
    schemas/        # Pydantic schemas
    services/       # Business logic + AI pipeline
    core/           # Config, auth, DB session
```
