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
        from app.models import user, reconciliation, contract  # noqa
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


# ── Contracts ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_and_list_contracts(client, db_session):
    """Create a contract and verify it appears in the list with balance info."""
    from app.models.reconciliation import BankAccount
    from app.models.user import User, UserRole
    from app.core.security import hash_password

    user = User(
        email="contracts@test.com",
        full_name="Contract User",
        hashed_password=hash_password("pass1234"),
        role=UserRole.PREPARER,
    )
    db_session.add(user)
    acct = BankAccount(
        name="Contracts Account", account_number="9999",
        masked_number="****9999", entity_name="Corp", currency="USD",
    )
    db_session.add(acct)
    await db_session.commit()

    r = await client.post("/api/auth/token", data={
        "username": "contracts@test.com", "password": "pass1234",
    })
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    r = await client.post("/api/contracts", json={
        "reference": "CNT-TEST-001",
        "name": "Test Infrastructure Contract",
        "counterparty": "BuildCo Ltd",
        "bank_account_id": acct.id,
        "deployed_amount": "500000.00",
        "contract_start": "2024-01-01",
        "contract_end": "2024-12-31",
        "scheduled_payment_amount": "50000.00",
        "payment_frequency": "monthly",
        "currency": "USD",
        "description": "Test contract for unit tests",
    }, headers=headers)
    assert r.status_code == 201
    data = r.json()
    assert data["reference"] == "CNT-TEST-001"
    assert float(data["deployed_amount"]) == 500000.0
    assert float(data["remaining_balance"]) == 500000.0
    assert float(data["used_amount"]) == 0.0

    # List contracts
    r = await client.get("/api/contracts", headers=headers)
    assert r.status_code == 200
    contracts = r.json()
    assert len(contracts) >= 1
    assert contracts[0]["reference"] == "CNT-TEST-001"


@pytest.mark.asyncio
async def test_contract_duplicate_reference_rejected(client, db_session):
    """Creating a contract with a duplicate reference should return 400."""
    from app.models.reconciliation import BankAccount
    from app.models.user import User, UserRole
    from app.core.security import hash_password

    user = User(
        email="dupcontract@test.com",
        full_name="Dup User",
        hashed_password=hash_password("pass1234"),
        role=UserRole.PREPARER,
    )
    db_session.add(user)
    acct = BankAccount(
        name="Dup Account", account_number="8888",
        masked_number="****8888", entity_name="Corp", currency="USD",
    )
    db_session.add(acct)
    await db_session.commit()

    r = await client.post("/api/auth/token", data={
        "username": "dupcontract@test.com", "password": "pass1234",
    })
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "reference": "CNT-DUP-001",
        "name": "Contract",
        "counterparty": "Corp",
        "bank_account_id": acct.id,
        "deployed_amount": "100000.00",
        "contract_start": "2024-01-01",
    }
    r1 = await client.post("/api/contracts", json=payload, headers=headers)
    assert r1.status_code == 201

    r2 = await client.post("/api/contracts", json=payload, headers=headers)
    assert r2.status_code == 400
    assert "already exists" in r2.json()["detail"]


@pytest.mark.asyncio
async def test_contract_balance_endpoint(client, db_session):
    """Contract balance endpoint returns remaining balance and payment counts."""
    from app.models.reconciliation import BankAccount
    from app.models.user import User, UserRole
    from app.core.security import hash_password
    from decimal import Decimal

    user = User(
        email="balance@test.com",
        full_name="Balance User",
        hashed_password=hash_password("pass1234"),
        role=UserRole.PREPARER,
    )
    db_session.add(user)
    acct = BankAccount(
        name="Bal Account", account_number="7777",
        masked_number="****7777", entity_name="Corp", currency="USD",
    )
    db_session.add(acct)
    await db_session.commit()

    r = await client.post("/api/auth/token", data={
        "username": "balance@test.com", "password": "pass1234",
    })
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Create contract
    r = await client.post("/api/contracts", json={
        "reference": "CNT-BAL-001",
        "name": "Balance Test Contract",
        "counterparty": "Corp",
        "bank_account_id": acct.id,
        "deployed_amount": "250000.00",
        "contract_start": "2024-01-01",
    }, headers=headers)
    contract_id = r.json()["id"]

    # Check balance
    r = await client.get(f"/api/contracts/{contract_id}/balance", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert float(data["deployed_amount"]) == 250000.0
    assert float(data["remaining_balance"]) == 250000.0
    assert data["is_overrun"] is False


@pytest.mark.asyncio
async def test_new_exception_types_in_ai_pipeline():
    """AI pipeline handles all 8 exception types without error."""
    from decimal import Decimal
    from app.services.ai_pipeline import generate_ai_explanation, suggest_journal_entry

    new_types = ["undocumented_expense", "stale_item", "contract_variance"]
    for exc_type in new_types:
        result = generate_ai_explanation(
            exception_type=exc_type,
            bank_date="2022-11-15",
            description="TEST TRANSACTION",
            amount=Decimal("1000.00"),
            ledger_amount=Decimal("900.00"),
        )
        assert "explanation" in result
        assert len(result["explanation"]) > 10

        journal = suggest_journal_entry(exc_type, Decimal("1000.00"), "TEST TRANSACTION")
        assert "suggested_debit" in journal
        assert "suggested_credit" in journal


# ── CSV Import ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_csv_import_bank_statement(client, db_session):
    """Upload a CSV bank statement and verify transactions + exceptions are created."""
    from app.models.reconciliation import BankAccount
    from app.models.user import User, UserRole
    from app.core.security import hash_password
    import io

    user = User(
        email="csvimport@test.com",
        full_name="CSV User",
        hashed_password=hash_password("pass1234"),
        role=UserRole.PREPARER,
    )
    db_session.add(user)
    acct = BankAccount(
        name="CSV Account", account_number="6666",
        masked_number="****6666", entity_name="Corp", currency="USD",
    )
    db_session.add(acct)
    await db_session.commit()

    r = await client.post("/api/auth/token", data={
        "username": "csvimport@test.com", "password": "pass1234",
    })
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Build CSV with 5 rows: 2 no-reference (→ undocumented_expense) + 3 normal
    csv_content = (
        "date,description,amount,reference\n"
        "2024-11-01,ACH PAYROLL,-42350.00,PR-11-01\n"
        "2024-11-03,CONSULTANT FEE,-5000.00,\n"
        "2024-11-05,STRIPE PAYOUT,18420.00,STR-3001\n"
        "2024-11-10,WIRE IN - CLIENT A,75000.00,WR-CA-02\n"
        "2024-11-28,BANK SERVICE CHARGE,-35.00,\n"
    )
    csv_bytes = csv_content.encode("utf-8")

    r = await client.post(
        "/api/import/bank-statement",
        data={
            "bank_account_id": str(acct.id),
            "period_start": "2024-11-01",
            "period_end": "2024-11-30",
        },
        files={"file": ("test_statement.csv", io.BytesIO(csv_bytes), "text/csv")},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["rows_imported"] == 5
    assert data["rows_skipped"] == 0
    # At least the 2 no-reference rows should be flagged
    assert data["exceptions"] >= 2
    assert data["matched"] + data["exceptions"] == 5
    assert data["reconciliation_id"] is not None


@pytest.mark.asyncio
async def test_csv_import_invalid_file_type(client, db_session):
    """Non-CSV upload is rejected with 400."""
    from app.models.reconciliation import BankAccount
    from app.models.user import User, UserRole
    from app.core.security import hash_password
    import io

    user = User(
        email="csvbadtype@test.com",
        full_name="Bad Type User",
        hashed_password=hash_password("pass1234"),
        role=UserRole.PREPARER,
    )
    db_session.add(user)
    acct = BankAccount(
        name="Bad Account", account_number="5555",
        masked_number="****5555", entity_name="Corp", currency="USD",
    )
    db_session.add(acct)
    await db_session.commit()

    r = await client.post("/api/auth/token", data={
        "username": "csvbadtype@test.com", "password": "pass1234",
    })
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    r = await client.post(
        "/api/import/bank-statement",
        data={
            "bank_account_id": str(acct.id),
            "period_start": "2024-11-01",
            "period_end": "2024-11-30",
        },
        files={"file": ("report.pdf", io.BytesIO(b"fake pdf content"), "application/pdf")},
        headers=headers,
    )
    assert r.status_code == 400
    assert "CSV" in r.json()["detail"]


@pytest.mark.asyncio
async def test_watsonx_explain_endpoint(client, db_session):
    """POST /api/watsonx/explain returns explanation, confidence, and journal entry."""
    from app.models.user import User, UserRole
    from app.core.security import hash_password

    user = User(
        email="watsonx@test.com",
        full_name="Watsonx User",
        hashed_password=hash_password("pass1234"),
        role=UserRole.PREPARER,
    )
    db_session.add(user)
    await db_session.commit()

    r = await client.post("/api/auth/token", data={
        "username": "watsonx@test.com", "password": "pass1234",
    })
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    r = await client.post("/api/watsonx/explain", json={
        "exception_type": "missing_entry",
        "bank_date": "2024-10-18",
        "description": "GOOGLE WORKSPACE",
        "amount": 840.00,
    }, headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "explanation" in data
    assert len(data["explanation"]) > 10
    assert "confidence" in data
    assert "journal" in data
    assert "suggested_debit" in data["journal"]
    assert "suggested_credit" in data["journal"]
