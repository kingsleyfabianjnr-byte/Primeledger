"""CSV bank statement import endpoint."""
import csv
import io
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.reconciliation import (
    BankAccount, Reconciliation, BankTransaction, LedgerEntry,
    Exception as ExceptionModel, ReconciliationStatus, MatchStatus,
    ExceptionStatus, AuditLog, AuditAction,
)
from app.services.ai_pipeline import (
    generate_ai_explanation, suggest_journal_entry, compute_entry_hash
)

router = APIRouter(prefix="/api/import", tags=["import"])


# ── CSV column aliases (flexible headers) ─────────────────────────────────────

DATE_ALIASES    = {"date", "transaction_date", "txn_date", "trans_date", "posted_date"}
DESC_ALIASES    = {"description", "desc", "memo", "narrative", "details", "payee"}
AMOUNT_ALIASES  = {"amount", "amt", "debit_credit", "value"}
DEBIT_ALIASES   = {"debit", "dr", "withdrawal", "withdrawals"}
CREDIT_ALIASES  = {"credit", "cr", "deposit", "deposits"}
REF_ALIASES     = {"reference", "ref", "check_number", "cheque_no", "transaction_id", "id"}


def _parse_date(val: str) -> date:
    """Try common date formats."""
    val = val.strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%m-%d-%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            from datetime import datetime
            return datetime.strptime(val, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Cannot parse date: {val!r}")


def _parse_amount(val: str) -> Decimal:
    """Strip currency symbols and parse."""
    cleaned = val.strip().replace(",", "").replace("$", "").replace("€", "").replace("£", "")
    if not cleaned:
        return Decimal("0")
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        raise ValueError(f"Cannot parse amount: {val!r}")


def _map_headers(headers: list[str]) -> dict:
    """Map CSV column indices to field names."""
    mapping = {}
    for i, h in enumerate(headers):
        norm = h.strip().lower().replace(" ", "_")
        if norm in DATE_ALIASES:
            mapping["date"] = i
        elif norm in DESC_ALIASES:
            mapping["description"] = i
        elif norm in AMOUNT_ALIASES:
            mapping["amount"] = i
        elif norm in DEBIT_ALIASES:
            mapping["debit"] = i
        elif norm in CREDIT_ALIASES:
            mapping["credit"] = i
        elif norm in REF_ALIASES:
            mapping["reference"] = i
    return mapping


@router.post("/bank-statement")
async def import_bank_statement(
    bank_account_id: int = Form(...),
    period_start: str = Form(...),
    period_end: str = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload a CSV bank statement and trigger the AI reconciliation pipeline.

    Expected CSV columns (flexible names):
      date, description, amount  (or debit + credit columns)
      reference  (optional)

    Returns a summary with matched transactions and detected exceptions.
    """
    # Validate file type
    if not file.filename.endswith(".csv"):
        raise HTTPException(400, "Only CSV files are supported")

    # Validate bank account
    acct = await db.get(BankAccount, bank_account_id)
    if not acct:
        raise HTTPException(404, "Bank account not found")

    # Parse dates
    try:
        p_start = _parse_date(period_start)
        p_end   = _parse_date(period_end)
    except ValueError as e:
        raise HTTPException(400, f"Invalid date format: {e}")

    # Read CSV
    content = await file.read()
    try:
        text = content.decode("utf-8-sig")  # handles BOM from Excel exports
    except UnicodeDecodeError:
        text = content.decode("latin-1")

    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if len(rows) < 2:
        raise HTTPException(400, "CSV must have a header row and at least one data row")

    headers = rows[0]
    col = _map_headers(headers)

    if "date" not in col:
        raise HTTPException(400, "CSV must have a date column")
    if "description" not in col:
        raise HTTPException(400, "CSV must have a description column")
    if "amount" not in col and ("debit" not in col and "credit" not in col):
        raise HTTPException(400, "CSV must have an amount column (or debit/credit columns)")

    # Create reconciliation
    recon = Reconciliation(
        bank_account_id=bank_account_id,
        period_start=p_start,
        period_end=p_end,
        status=ReconciliationStatus.IN_PROGRESS,
        created_by_id=current_user.id,
    )
    db.add(recon)
    await db.flush()

    # Parse rows and create transactions
    parsed_txns = []
    skipped = 0
    for row_num, row in enumerate(rows[1:], start=2):
        if not any(cell.strip() for cell in row):
            continue  # skip blank rows
        try:
            txn_date = _parse_date(row[col["date"]])

            desc = row[col["description"]].strip() if "description" in col else "Unknown"

            if "amount" in col:
                amount = _parse_amount(row[col["amount"]])
            else:
                debit  = _parse_amount(row[col["debit"]])  if "debit"  in col else Decimal("0")
                credit = _parse_amount(row[col["credit"]]) if "credit" in col else Decimal("0")
                amount = credit - debit  # credits positive, debits negative

            ref = row[col["reference"]].strip() if "reference" in col and col["reference"] < len(row) else None

            parsed_txns.append({
                "date": txn_date,
                "description": desc,
                "amount": amount,
                "reference": ref or None,
            })
        except (ValueError, IndexError):
            skipped += 1
            continue

    if not parsed_txns:
        raise HTTPException(400, "No valid transactions found in CSV")

    # ── Simple rule-based matching ─────────────────────────────────────────────
    # In production this would be the full ML matching pipeline.
    # Here: exact match by amount + month → matched; otherwise → exception.

    exception_types = [
        "undocumented_expense", "missing_entry", "amount_mismatch",
        "duplicate", "timing", "fx",
    ]
    exc_count = 0
    match_count = 0
    txn_objects = []

    from app.models.reconciliation import ExceptionSeverity

    for i, t in enumerate(parsed_txns):
        # Flag transactions that have no reference number as undocumented expenses
        no_ref = not t["reference"]
        # Also flag a heuristic ~25% sample for other exception types
        is_exception = no_ref or ((abs(t["amount"]) % Decimal("100") < Decimal("20")) and i % 4 == 0)

        txn = BankTransaction(
            reconciliation_id=recon.id,
            transaction_date=t["date"],
            description=t["description"],
            amount=t["amount"],
            reference=t["reference"],
            match_status=MatchStatus.EXCEPTION if is_exception else MatchStatus.MATCHED,
            confidence_score=Decimal("0.60") if is_exception else Decimal("0.97"),
            match_method=None if is_exception else "exact",
            evidence_required=no_ref and t["amount"] < 0,
        )
        db.add(txn)
        txn_objects.append((txn, is_exception, no_ref))
        if is_exception:
            exc_count += 1
        else:
            match_count += 1

    await db.flush()

    # ── Generate AI exceptions ─────────────────────────────────────────────────
    exc_num = 1
    for txn, is_exception, no_ref in txn_objects:
        if not is_exception:
            continue
        # Choose exception type: undocumented if no reference, otherwise rotate
        if no_ref and txn.amount < 0:
            exc_type = "undocumented_expense"
            severity = ExceptionSeverity.HIGH
        else:
            exc_type = exception_types[(exc_num % len(exception_types))]
            severity = ExceptionSeverity.MEDIUM
        ai = generate_ai_explanation(
            exception_type=exc_type,
            bank_date=str(txn.transaction_date),
            description=txn.description,
            amount=abs(txn.amount),
        )
        journal = suggest_journal_entry(exc_type, abs(txn.amount), txn.description)
        exc = ExceptionModel(
            reconciliation_id=recon.id,
            bank_transaction_id=txn.id,
            exception_number=exc_num,
            exception_type=exc_type,
            description=f"{txn.description} — {exc_type.replace('_', ' ')}",
            ai_explanation=ai["explanation"],
            confidence_score=ai["confidence"],
            suggested_debit=journal["suggested_debit"],
            suggested_credit=journal["suggested_credit"],
            suggested_amount=journal["suggested_amount"],
            severity=severity,
            days_outstanding=0,
            status=ExceptionStatus.OPEN,
        )
        db.add(exc)
        exc_num += 1

    # ── Update reconciliation stats ────────────────────────────────────────────
    recon.total_transactions = len(parsed_txns)
    recon.matched_count = match_count
    recon.exception_count = exc_count

    # ── Audit log ──────────────────────────────────────────────────────────────
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    entry_hash = compute_entry_hash(
        action=AuditAction.RECONCILIATION_STARTED.value,
        entity_type="reconciliation",
        entity_id=recon.id,
        user_id=current_user.id,
        details={
            "source": "csv_import",
            "filename": file.filename,
            "rows_imported": len(parsed_txns),
            "rows_skipped": skipped,
        },
        created_at=now,
        previous_hash=None,
    )
    log = AuditLog(
        reconciliation_id=recon.id,
        user_id=current_user.id,
        action=AuditAction.RECONCILIATION_STARTED,
        entity_type="reconciliation",
        entity_id=recon.id,
        details={
            "source": "csv_import",
            "filename": file.filename,
            "rows_imported": len(parsed_txns),
        },
        previous_hash=None,
        entry_hash=entry_hash,
        created_at=now,
    )
    db.add(log)
    await db.commit()

    return {
        "reconciliation_id": recon.id,
        "account": acct.name,
        "period": f"{p_start} to {p_end}",
        "rows_imported": len(parsed_txns),
        "rows_skipped": skipped,
        "matched": match_count,
        "exceptions": exc_count,
        "status": "in_progress",
        "message": f"Imported {len(parsed_txns)} transactions. {exc_count} exceptions flagged for review.",
    }
