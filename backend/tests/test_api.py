"""Backend tests."""
import pytest
import pytest_asyncio
from datetime import date
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.main import app
from app.core.database import get_db, Base

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="function")
async def db_session():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        from app.models import user, reconciliation  # noqa
        await conn.run_sync(Base.metadata.create_all)

    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


# ── Health check ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# ── Auth ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_register_and_login(client):
    # Register
    r = await client.post("/api/auth/register", json={
        "email": "test@example.com",
        "full_name": "Test User",
        "password": "securepass123",
        "role": "preparer",
    })
    assert r.status_code == 201
    data = r.json()
    assert data["email"] == "test@example.com"
    assert data["role"] == "preparer"

    # Login
    r = await client.post("/api/auth/token", data={
        "username": "test@example.com",
        "password": "securepass123",
    })
    assert r.status_code == 200
    token = r.json()["access_token"]
    assert token

    # Get me
    r = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["email"] == "test@example.com"


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    await client.post("/api/auth/register", json={
        "email": "test2@example.com",
        "full_name": "Test User 2",
        "password": "correctpass",
        "role": "preparer",
    })
    r = await client.post("/api/auth/token", data={
        "username": "test2@example.com",
        "password": "wrongpass",
    })
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_me_unauthenticated(client):
    r = await client.get("/api/auth/me")
    assert r.status_code == 401


# ── Reconciliations ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_and_list_reconciliation(client, db_session):
    from app.models.reconciliation import BankAccount
    from app.core.security import hash_password
    from app.models.user import User, UserRole

    # Create user + bank account directly
    user = User(
        email="recon@test.com",
        full_name="Recon User",
        hashed_password=hash_password("pass1234"),
        role=UserRole.PREPARER,
    )
    db_session.add(user)
    acct = BankAccount(
        name="Test Account",
        account_number="1234567890",
        masked_number="****7890",
        entity_name="Test Corp",
        currency="USD",
    )
    db_session.add(acct)
    await db_session.commit()

    # Login
    r = await client.post("/api/auth/token", data={
        "username": "recon@test.com",
        "password": "pass1234",
    })
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Create reconciliation
    r = await client.post("/api/reconciliations", json={
        "bank_account_id": acct.id,
        "period_start": "2024-11-01",
        "period_end": "2024-11-30",
    }, headers=headers)
    assert r.status_code == 201
    data = r.json()
    assert data["status"] == "pending"
    assert data["bank_account_id"] == acct.id

    # List reconciliations
    r = await client.get("/api/reconciliations", headers=headers)
    assert r.status_code == 200
    assert len(r.json()) >= 1


# ── Exceptions ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_exception_review_requires_approver(client, db_session):
    """Preparers cannot approve exceptions."""
    from app.models.reconciliation import (
        BankAccount, Reconciliation, Exception as Exc,
        ReconciliationStatus, ExceptionStatus,
    )
    from app.models.user import User, UserRole
    from app.core.security import hash_password
    from decimal import Decimal

    preparer = User(
        email="prep@test.com",
        full_name="Preparer",
        hashed_password=hash_password("prep1234"),
        role=UserRole.PREPARER,
    )
    db_session.add(preparer)
    acct = BankAccount(
        name="Acct", account_number="111", masked_number="***1",
        entity_name="Corp", currency="USD",
    )
    db_session.add(acct)
    await db_session.flush()

    recon = Reconciliation(
        bank_account_id=acct.id,
        period_start=date(2024, 10, 1),
        period_end=date(2024, 10, 31),
        status=ReconciliationStatus.IN_PROGRESS,
        created_by_id=preparer.id,
    )
    db_session.add(recon)
    await db_session.flush()

    exc = Exc(
        reconciliation_id=recon.id,
        exception_number=1,
        exception_type="timing",
        description="Test exception",
        ai_explanation="AI found this",
        confidence_score=Decimal("0.90"),
        status=ExceptionStatus.OPEN,
    )
    db_session.add(exc)
    await db_session.commit()

    # Login as preparer
    r = await client.post("/api/auth/token", data={
        "username": "prep@test.com",
        "password": "prep1234",
    })
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Attempt to approve — should be forbidden
    r = await client.post(f"/api/exceptions/{exc.id}/review", json={
        "action": "approve",
    }, headers=headers)
    assert r.status_code == 403


# ── Audit trail ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_audit_log_requires_auth(client):
    r = await client.get("/api/audit")
    assert r.status_code == 401


# ── AI pipeline service ───────────────────────────────────────────────────────

def test_generate_ai_explanation():
    from decimal import Decimal
    from app.services.ai_pipeline import generate_ai_explanation

    result = generate_ai_explanation(
        exception_type="timing",
        bank_date="2024-10-31",
        description="SVC CHG MONTHLY",
        amount=Decimal("35.00"),
    )
    assert "explanation" in result
    assert "confidence" in result
    assert result["confidence"] > 0


def test_suggest_journal_entry():
    from decimal import Decimal
    from app.services.ai_pipeline import suggest_journal_entry

    result = suggest_journal_entry("timing", Decimal("35.00"), "SVC CHG")
    assert "suggested_debit" in result
    assert "suggested_credit" in result
    assert result["suggested_amount"] == Decimal("35.00")


def test_hash_chain():
    from datetime import datetime, timezone
    from app.services.ai_pipeline import compute_entry_hash

    h1 = compute_entry_hash(
        action="match_created",
        entity_type="transaction",
        entity_id=1,
        user_id=None,
        details={},
        created_at=datetime(2024, 10, 1, tzinfo=timezone.utc),
        previous_hash=None,
    )
    h2 = compute_entry_hash(
        action="exception_raised",
        entity_type="exception",
        entity_id=1,
        user_id=1,
        details={"type": "timing"},
        created_at=datetime(2024, 10, 1, 1, tzinfo=timezone.utc),
        previous_hash=h1,
    )
    assert len(h1) == 64
    assert len(h2) == 64
    assert h1 != h2
