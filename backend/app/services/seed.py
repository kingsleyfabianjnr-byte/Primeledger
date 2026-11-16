"""Seed service — populates DB with realistic demo data."""
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.user import User, UserRole
from app.models.reconciliation import (
    BankAccount, Reconciliation, BankTransaction, LedgerEntry, Exception,
    AuditLog, ReconciliationStatus, MatchStatus, ExceptionStatus, ExceptionSeverity,
    AuditAction,
)
from app.models.contract import Contract, ContractPayment, ContractStatus, PaymentStatus
from app.core.security import hash_password
from app.services.ai_pipeline import (
    generate_ai_explanation, suggest_journal_entry, compute_entry_hash
)


DEMO_TRANSACTIONS = [
    {"date": date(2024, 10, 1),  "desc": "ACH PAYROLL 10/01",        "amount": Decimal("-42350.00"), "ref": "PR-10-01"},
    {"date": date(2024, 10, 3),  "desc": "SVC CHG MONTHLY",          "amount": Decimal("-35.00"),    "ref": None},         # undocumented — no ref
    {"date": date(2024, 10, 5),  "desc": "STRIPE PAYOUT",            "amount": Decimal("18420.00"),  "ref": "STR-2041"},
    {"date": date(2024, 10, 8),  "desc": "AMAZON WEB SERVICES",      "amount": Decimal("-1247.33"),  "ref": "AWS-OCT"},
    {"date": date(2024, 10, 10), "desc": "WIRE IN - CLIENT A",       "amount": Decimal("75000.00"),  "ref": "WR-CA-01"},
    {"date": date(2024, 10, 12), "desc": "OFFICE LEASE OCT",         "amount": Decimal("-8500.00"),  "ref": "LSE-OCT"},
    {"date": date(2024, 10, 15), "desc": "ACH PAYROLL 10/15",        "amount": Decimal("-42350.00"), "ref": "PR-10-15"},
    {"date": date(2024, 10, 18), "desc": "GOOGLE WORKSPACE",         "amount": Decimal("-840.00"),   "ref": "GWS-OCT"},
    {"date": date(2024, 10, 20), "desc": "STRIPE PAYOUT",            "amount": Decimal("22100.00"),  "ref": "STR-2042"},
    {"date": date(2024, 10, 22), "desc": "INSURANCE PREMIUM",        "amount": Decimal("-3200.00"),  "ref": "INS-Q4"},
    {"date": date(2024, 10, 25), "desc": "CONTRACT PMT - CNT-2024-001", "amount": Decimal("-70000.00"), "ref": "CNT-2024-001-OCT"},  # contract payment
    {"date": date(2024, 10, 28), "desc": "UTILITY BILL OCT",         "amount": Decimal("-412.75"),   "ref": "UTL-OCT"},
    {"date": date(2024, 10, 31), "desc": "SVC CHG MONTHLY",          "amount": Decimal("-35.00"),    "ref": "SVC-1031b"},
    {"date": date(2024, 10, 31), "desc": "INTEREST CREDIT",          "amount": Decimal("127.50"),    "ref": "INT-OCT"},
    # Stale item from FY 2022 — surfaced during current reconciliation review
    {"date": date(2022, 11, 15), "desc": "VENDOR REFUND UNPROCESSED", "amount": Decimal("1800.00"),  "ref": None},
]

EXCEPTIONS_DATA = [
    {
        "txn_index": 1,   # SVC CHG MONTHLY Oct 3 — no reference number
        "type": "undocumented_expense",
        "desc": "Service charge of $35.00 posted without reference number or receipt",
        "exception_number": 1,
        "severity": ExceptionSeverity.HIGH,
        "days_outstanding": 0,
    },
    {
        "txn_index": 7,   # Google Workspace — no ledger entry
        "type": "missing_entry",
        "desc": "Google Workspace charge has no corresponding ledger entry",
        "exception_number": 2,
        "severity": ExceptionSeverity.MEDIUM,
        "days_outstanding": 0,
    },
    {
        "txn_index": 9,   # Insurance Premium — amount mismatch $3,200 vs $3,150
        "type": "amount_mismatch",
        "desc": "Insurance amount in bank ($3,200) differs from ledger ($3,150)",
        "exception_number": 3,
        "severity": ExceptionSeverity.MEDIUM,
        "days_outstanding": 0,
        "ledger_amount": Decimal("3150.00"),
    },
    {
        "txn_index": 10,  # CONTRACT PMT - $70,000 vs scheduled $70,000 — exact match (shows in UI as matched)
        "type": "contract_variance",
        "desc": "Contract payment of $70,000 matches schedule but requires contract balance confirmation",
        "exception_number": 4,
        "severity": ExceptionSeverity.MEDIUM,
        "days_outstanding": 0,
        "ledger_amount": Decimal("70000.00"),
    },
    {
        "txn_index": 11,  # Utility Bill — no ledger entry
        "type": "missing_entry",
        "desc": "Utility bill missing from general ledger",
        "exception_number": 5,
        "severity": ExceptionSeverity.LOW,
        "days_outstanding": 0,
    },
    {
        "txn_index": 12,  # SVC CHG MONTHLY Oct 31 — possible duplicate of #1
        "type": "duplicate",
        "desc": "Possible duplicate of Oct 3 service charge — same amount, same description",
        "exception_number": 6,
        "severity": ExceptionSeverity.HIGH,
        "days_outstanding": 0,
    },
    {
        "txn_index": 13,  # Interest Credit — FX difference
        "type": "fx",
        "desc": "Interest credit contains FX translation difference",
        "exception_number": 7,
        "severity": ExceptionSeverity.LOW,
        "days_outstanding": 0,
    },
    {
        "txn_index": 14,  # Stale item from FY 2022
        "type": "stale_item",
        "desc": "Vendor refund from Nov 2022 was never reconciled — 730+ days outstanding",
        "exception_number": 8,
        "severity": ExceptionSeverity.CRITICAL,
        "days_outstanding": 730,
        "original_fiscal_year": 2022,
    },
]


async def seed_demo_data(db: AsyncSession) -> None:
    """Idempotent seed — skips if data already exists."""
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

    # ── Contracts ─────────────────────────────────────────────────────────────
    # Contract CNT-2024-001: $700,000 deployed, $70,000/month over 10 months
    contract_a = Contract(
        reference="CNT-2024-001",
        name="Infrastructure Services Agreement",
        counterparty="BuildCorp Solutions Ltd",
        bank_account_id=accounts[0].id,
        deployed_amount=Decimal("700000.00"),
        used_amount=Decimal("210000.00"),   # 3 prior payments already matched
        contract_start=date(2024, 1, 1),
        contract_end=date(2024, 10, 31),
        scheduled_payment_amount=Decimal("70000.00"),
        payment_frequency="monthly",
        currency="USD",
        description="10-month infrastructure contract. Monthly drawdown of $70,000 from initial deployed fund of $700,000.",
        status=ContractStatus.ACTIVE,
        created_by_id=admin.id,
    )
    # Contract CNT-2023-007: older contract, fully serviced
    contract_b = Contract(
        reference="CNT-2023-007",
        name="IT Consulting Retainer",
        counterparty="TechConsult Group",
        bank_account_id=accounts[0].id,
        deployed_amount=Decimal("240000.00"),
        used_amount=Decimal("240000.00"),   # fully consumed
        contract_start=date(2023, 1, 1),
        contract_end=date(2023, 12, 31),
        scheduled_payment_amount=Decimal("20000.00"),
        payment_frequency="monthly",
        currency="USD",
        description="12-month IT consulting retainer. All payments processed and reconciled.",
        status=ContractStatus.COMPLETED,
        created_by_id=admin.id,
    )
    db.add_all([contract_a, contract_b])
    await db.flush()

    # Seed prior matched payments for contract_a (Jan–Mar 2024, already processed)
    for month_offset, period in enumerate([date(2024, 1, 1), date(2024, 2, 1), date(2024, 3, 1)]):
        p = ContractPayment(
            contract_id=contract_a.id,
            period_month=period,
            expected_amount=Decimal("70000.00"),
            actual_amount=Decimal("70000.00"),
            status=PaymentStatus.MATCHED,
            notes=f"Payment matched — {period.strftime('%B %Y')}",
        )
        db.add(p)

    # Oct 2024 expected payment (will be matched during this reconciliation)
    oct_payment = ContractPayment(
        contract_id=contract_a.id,
        period_month=date(2024, 10, 1),
        expected_amount=Decimal("70000.00"),
        status=PaymentStatus.EXPECTED,
    )
    db.add(oct_payment)
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

    # Completed September 2024
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

    # Payroll account
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
        evidence_required = t["ref"] is None and t["amount"] < 0  # expenses with no ref
        txn = BankTransaction(
            reconciliation_id=recon.id,
            transaction_date=t["date"],
            description=t["desc"],
            amount=t["amount"],
            reference=t.get("ref"),
            match_status=status,
            confidence_score=Decimal("0.98") if status == MatchStatus.MATCHED else Decimal("0.60"),
            match_method="exact" if status == MatchStatus.MATCHED else None,
            evidence_required=evidence_required,
        )
        db.add(txn)
        txn_objects.append(txn)
    await db.flush()

    # Link contract payment transaction to contract
    contract_txn = txn_objects[10]  # CONTRACT PMT - CNT-2024-001
    contract_txn.contract_id = contract_a.id
    oct_payment.bank_transaction_id = contract_txn.id

    # ── Exceptions ────────────────────────────────────────────────────────────
    exc_objects = []
    for exc_data in EXCEPTIONS_DATA:
        txn = txn_objects[exc_data["txn_index"]]
        ledger_amt = exc_data.get("ledger_amount")
        ai = generate_ai_explanation(
            exception_type=exc_data["type"],
            bank_date=str(txn.transaction_date),
            description=txn.description,
            amount=abs(txn.amount),
            ledger_amount=ledger_amt,
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
            severity=exc_data.get("severity", ExceptionSeverity.MEDIUM),
            days_outstanding=exc_data.get("days_outstanding", 0),
            original_fiscal_year=exc_data.get("original_fiscal_year"),
            status=ExceptionStatus.OPEN,
        )
        # Link contract_variance exception to the contract
        if exc_data["type"] == "contract_variance":
            exc.contract_id = contract_a.id
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
                "type": "undocumented_expense",
                "severity": "high",
                "confidence": 0.96,
                "description": exc_objects[0].description,
            },
            "created_at": datetime(2024, 11, 1, 8, 2, tzinfo=timezone.utc),
        },
        {
            "action": AuditAction.EXCEPTION_RAISED,
            "entity_type": "exception",
            "entity_id": exc_objects[7].id,
            "user_id": None,
            "details": {
                "type": "stale_item",
                "severity": "critical",
                "days_outstanding": 730,
                "original_fiscal_year": 2022,
                "description": exc_objects[7].description,
            },
            "created_at": datetime(2024, 11, 1, 8, 3, tzinfo=timezone.utc),
        },
        {
            "action": AuditAction.ENTRY_APPROVED,
            "entity_type": "exception",
            "entity_id": exc_objects[1].id,
            "user_id": approver.id,
            "details": {
                "exception_number": exc_objects[1].exception_number,
                "reviewer_note": "Confirmed with vendor — correct amount",
            },
            "created_at": datetime(2024, 11, 1, 10, 30, tzinfo=timezone.utc),
        },
        {
            "action": AuditAction.ENTRY_EDITED,
            "entity_type": "exception",
            "entity_id": exc_objects[2].id,
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
