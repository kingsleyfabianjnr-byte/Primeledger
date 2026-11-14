"""FastAPI application entry point."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import init_db
from app.api import auth, dashboard, exceptions, reconciliations, audit, watsonx, csv_import, export


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    # Seed demo data
    from app.core.database import AsyncSessionLocal
    from app.services.seed import seed_demo_data
    async with AsyncSessionLocal() as db:
        await seed_demo_data(db)
    yield
    # Shutdown (nothing needed for SQLite)


app = FastAPI(
    title=settings.APP_NAME,
    description="Agentic bank reconciliation powered by IBM watsonx.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(exceptions.router)
app.include_router(reconciliations.router)
app.include_router(audit.router)
app.include_router(watsonx.router)
app.include_router(csv_import.router)
app.include_router(export.router)


@app.get("/health")
async def health():
    return {"status": "ok", "app": settings.APP_NAME}
