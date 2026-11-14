"""Seed service — populates DB with realistic demo data."""
from datetime import date, datetime, timezone
from decimal import Decimal
import random

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.user import User, UserRole
from app.models.reconciliation import (
    BankAccount, Reconciliation, BankTransaction, LedgerEntry, Exception,
    AuditLog, ReconciliationStatus, MatchStatus, ExceptionStatus, AuditAction,
)
from app.core.security import hash_password
from app.services.ai_pipeline import (
    generate_ai_explanation, suggest_journal_entry, compute_entry_hash
)


DEMO_TRANSACTIONS = [
    {"date": date(2024, 10, 1), "desc": "ACH PAYROLL 10/01", "amount": Decimal("-42350.00"), "ref": "PR-10-01"},
    {"date": date(2024, 10, 3), "desc": "SVC CHG MONTHLY", "amount": Decimal("-35.00"), "ref": "SVC-1031"},
    {"date": date(2024, 10, 5), "desc": "STRIPE PAYOUT", "amount": Decimal("18420.00"), "ref": "STR-2041"},
    {"date": date(2024, 10, 8), "desc": "AMAZON WEB SERVICES", "amount": Decimal("-1247.33"), "ref": "AWS-OCT"},
    {"date": date(2024, 10, 10), "desc": "WIRE IN - CLIENT A", "amount": Decimal("75000.00"), "ref": "WR-CA-01"},
    {"date": date(2024, 10, 12), "desc": "OFFICE LEASE OCT", "amount": Decimal("-8500.00"), "ref": "LSE-OCT"},
    {"date": date(2024, 10, 15), "desc": "ACH PAYROLL 10/15", "amount": Decimal("-42350.00"), "ref": "PR-10-15"},
    {"date": date(2024, 10, 18), "desc": "GOOGLE WORKSPACE", "amount": Decimal("-840.00"), "ref": "GWS-OCT"},
    {"date": date(2024, 10, 20), "desc": "STRIPE PAYOUT", "amount": Decimal("22100.00"), "ref": "STR-2042"},
    {"date": date(2024, 10, 22), "desc": "INSURANCE PREMIUM", "amount": Decimal("-3200.00"), "ref": "INS-Q4"},
    {"date": date(2024, 10, 25), "desc": "WIRE IN - CLIENT B", "amount": Decimal("50000.00"), "ref": "WR-CB-01"},
    {"date": date(2024, 10, 28), "desc": "UTILITY BILL OCT", "amount": Decimal("-412.75"), "ref": "UTL-OCT"},
    {"date": date(2024, 10, 31), "desc": "SVC CHG MONTHLY", "amount": Decimal("-35.00"), "ref": "SVC-1031b"},
    {"date": date(2024, 10, 31), "desc": "INTEREST CREDIT", "amount": Decimal("127.50"), "ref": "INT-OCT"},
]

EXCEPTIONS_DATA = [
    {
        "txn_index": 1,  # SVC CHG MONTHLY Oct 3
        "type": "timing",
        "desc": "Bank fee Oct 31 — No matching entry",
        "exception_number": 3,
    },
    {
        "txn_index": 12,  # SVC CHG MONTHLY Oct 31
        "type": "duplicate",
        "desc": "Possible duplicate of Oct 3 service charge",
        "exception_number": 5,
    },
    {
        "txn_index": 7,  # Google Workspace
        "type": "missing_entry",
        "desc": "Google Workspace charge has no corresponding ledger entry",
        "exception_number": 1,
    },
    {
        "txn_index": 9,  # Insurance Premium
        "type": "amount_mismatch",
        "desc": "Insurance amount in bank ($3,200) differs from ledger ($3,150)",
        "exception_number": 2,
    },
    {
        "txn_index": 13,  # Interest Credit
        "type": "fx",
        "desc": "Interest credit contains FX translation difference",
        "exception_number": 4,
    },
    {
        "txn_index": 11,  # Utility
        "type": "missing_entry",
        "desc": "Utility bill missing from general ledger",
        "exception_number": 6,
    },
    {
        "txn_index": 3,  # Stripe payout
        "type": "timing",
        "desc": "Stripe payout crosses period boundary",
        "exception_number": 7,
    },
]


async def seed_demo_data(db: AsyncSession) -> None:
    """Idempotent seed — skips if data already exists."""
    # Check if already seeded
    result = await db.execute(select(User).where(User.email == "demo@primeledger.ai"))
    if result.scalar_one_or_none():
        return

    # ── Users ────────────────────────────────────────────────────────────────
    admin = User(
        email="admin@primeledger.ai",
        full_name="Alex Admin",
        hashed_password=hash_password("admin123"),
        role=UserRole.ADMIN,
    )
    preparer = User(
        email="demo@primeledger.ai",
        full_name="Jordan Preparer",
        hashed_password=hash_password("demo1234"),
        role=UserRole.PREPARER,
    )
    approver = User(
        email="approver@primeledger.ai",
        full_name="Sam Approver",
        hashed_password=hash_password("approver123"),
        role=UserRole.APPROVER,
    )
    db.add_all([admin, preparer, approver])
    await db.flush()

    # ── Bank accounts ─────────────────────────────────────────────────────────
    accounts = [
        BankAccount(
            name="Operating Account",
            account_number="1000234567",
            masked_number="****4567",
            entity_name="PrimeLedger Inc.",
            currency="USD",
        ),
        BankAccount(
            name="Payroll Account",
            account_number="1000234890",
            masked_number="****4890",
            entity_name="PrimeLedger Inc.",
            currency="USD",
        ),
        BankAccount(
            name="EUR Collections",
            account_number="2000098712",
            masked_number="****8712",
            entity_name="PrimeLedger Europe BV",
            currency="EUR",
        ),
    ]
    db.add_all(accounts)
    await db.flush()

    # ── Reconciliation for October 2024 ──────────────────────────────────────
    recon = Reconciliation(
        bank_account_id=accounts[0].id,
        period_start=date(2024, 10, 1),
        period_end=date(2024, 10, 31),
        status=ReconciliationStatus.IN_PROGRESS,
        total_transactions=len(DEMO_TRANSACTIONS),
        matched_count=len(DEMO_TRANSACTIONS) - len(EXCEPTIONS_DATA),
        exception_count=len(EXCEPTIONS_DATA),
        bank_balance=Decimal("67054.42"),
        ledger_balance=Decimal("66926.92"),
        created_by_id=preparer.id,
    )
    db.add(recon)
    await db.flush()

    # ── A second completed reconciliation ─────────────────────────────────────
    recon_sep = Reconciliation(
        bank_account_id=accounts[0].id,
        period_start=date(2024, 9, 1),
        period_end=date(2024, 9, 30),
        status=ReconciliationStatus.APPROVED,
        total_transactions=12,
        matched_count=12,
        exception_count=0,
        bank_balance=Decimal("42100.00"),
        ledger_balance=Decimal("42100.00"),
        created_by_id=preparer.id,
        completed_at=datetime(2024, 10, 2, 9, 15, tzinfo=timezone.utc),
    )
    db.add(recon_sep)

    # Payroll account reconciliation
    recon_payroll = Reconciliation(
        bank_account_id=accounts[1].id,
        period_start=date(2024, 10, 1),
        period_end=date(2024, 10, 31),
        status=ReconciliationStatus.AWAITING_APPROVAL,
        total_transactions=4,
        matched_count=4,
        exception_count=0,
        bank_balance=Decimal("84700.00"),
        ledger_balance=Decimal("84700.00"),
        created_by_id=preparer.id,
    )
    db.add(recon_payroll)
    await db.flush()

    # ── Bank transactions ─────────────────────────────────────────────────────
    exception_txn_indices = {e["txn_index"] for e in EXCEPTIONS_DATA}
    txn_objects = []
    for i, t in enumerate(DEMO_TRANSACTIONS):
        status = MatchStatus.EXCEPTION if i in exception_txn_indices else MatchStatus.MATCHED
        txn = BankTransaction(
            reconciliation_id=recon.id,
            transaction_date=t["date"],
            description=t["desc"],
            amount=t["amount"],
            reference=t["ref"],
            match_status=status,
            confidence_score=Decimal("0.98") if status == MatchStatus.MATCHED else Decimal("0.60"),
            match_method="exact" if status == MatchStatus.MATCHED else None,
        )
        db.add(txn)
        txn_objects.append(txn)
    await db.flush()

    # ── Exceptions ────────────────────────────────────────────────────────────
    exc_objects = []
    for exc_data in EXCEPTIONS_DATA:
        txn = txn_objects[exc_data["txn_index"]]
        ai = generate_ai_explanation(
            exception_type=exc_data["type"],
            bank_date=str(txn.transaction_date),
            description=txn.description,
            amount=abs(txn.amount),
        )
        journal = suggest_journal_entry(exc_data["type"], abs(txn.amount), txn.description)
        exc = Exception(
            reconciliation_id=recon.id,
            bank_transaction_id=txn.id,
            exception_number=exc_data["exception_number"],
            exception_type=exc_data["type"],
            description=exc_data["desc"],
            ai_explanation=ai["explanation"],
            confidence_score=ai["confidence"],
            suggested_debit=journal["suggested_debit"],
            suggested_credit=journal["suggested_credit"],
            suggested_amount=journal["suggested_amount"],
            status=ExceptionStatus.OPEN,
        )
        db.add(exc)
        exc_objects.append(exc)
    await db.flush()

    # ── Audit log (hash chain) ────────────────────────────────────────────────
    prev_hash = None
    audit_entries = [
        {
            "action": AuditAction.RECONCILIATION_STARTED,
            "entity_type": "reconciliation",
            "entity_id": recon.id,
            "user_id": preparer.id,
            "details": {"period": "October 2024", "account": "Operating Account ****4567"},
            "created_at": datetime(2024, 11, 1, 8, 0, tzinfo=timezone.utc),
        },
        {
            "action": AuditAction.MATCH_CREATED,
            "entity_type": "bank_transaction",
            "entity_id": txn_objects[0].id,
            "user_id": None,
            "details": {"method": "exact", "confidence": 0.98, "description": "ACH PAYROLL 10/01"},
            "created_at": datetime(2024, 11, 1, 8, 1, tzinfo=timezone.utc),
        },
        {
            "action": AuditAction.EXCEPTION_RAISED,
            "entity_type": "exception",
            "entity_id": exc_objects[0].id,
            "user_id": None,
            "details": {
                "type": "timing",
                "confidence": 0.94,
                "description": exc_objects[0].description,
            },
            "created_at": datetime(2024, 11, 1, 8, 2, tzinfo=timezone.utc),
        },
        {
            "action": AuditAction.ENTRY_APPROVED,
            "entity_type": "exception",
            "entity_id": exc_objects[2].id,
            "user_id": approver.id,
            "details": {
                "exception_number": exc_objects[2].exception_number,
                "reviewer_note": "Confirmed with vendor — correct amount",
            },
            "created_at": datetime(2024, 11, 1, 10, 30, tzinfo=timezone.utc),
        },
        {
            "action": AuditAction.ENTRY_EDITED,
            "entity_type": "exception",
            "entity_id": exc_objects[1].id,
            "user_id": preparer.id,
            "details": {
                "field": "suggested_amount",
                "old_value": "3200.00",
                "new_value": "3150.00",
            },
            "created_at": datetime(2024, 11, 1, 11, 0, tzinfo=timezone.utc),
        },
    ]

    for entry in audit_entries:
        entry_hash = compute_entry_hash(
            action=entry["action"].value,
            entity_type=entry["entity_type"],
            entity_id=entry["entity_id"],
            user_id=entry["user_id"],
            details=entry["details"],
            created_at=entry["created_at"],
            previous_hash=prev_hash,
        )
        log = AuditLog(
            reconciliation_id=recon.id,
            user_id=entry["user_id"],
            action=entry["action"],
            entity_type=entry["entity_type"],
            entity_id=entry["entity_id"],
            details=entry["details"],
            previous_hash=prev_hash,
            entry_hash=entry_hash,
            created_at=entry["created_at"],
        )
        db.add(log)
        prev_hash = entry_hash

    await db.commit()
