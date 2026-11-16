"""Exception queue routes."""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User, UserRole
from app.models.reconciliation import (
    Exception as ExceptionModel, ExceptionStatus, AuditLog, AuditAction,
    BankTransaction,
)
from app.schemas.reconciliation import ExceptionRead, ExceptionReview
from app.services.ai_pipeline import compute_entry_hash

router = APIRouter(prefix="/api/exceptions", tags=["exceptions"])


def _to_read(exc: ExceptionModel) -> ExceptionRead:
    """Convert ORM exception to ExceptionRead, populating bank transaction fields."""
    bt = exc.bank_transaction
    data = {
        "id": exc.id,
        "reconciliation_id": exc.reconciliation_id,
        "bank_transaction_id": exc.bank_transaction_id,
        "exception_number": exc.exception_number,
        "exception_type": exc.exception_type,
        "description": exc.description,
        "ai_explanation": exc.ai_explanation,
        "confidence_score": exc.confidence_score,
        "suggested_debit": exc.suggested_debit,
        "suggested_credit": exc.suggested_credit,
        "suggested_amount": exc.suggested_amount,
        "status": exc.status,
        "reviewed_by_id": exc.reviewed_by_id,
        "reviewed_at": exc.reviewed_at,
        "reviewer_note": exc.reviewer_note,
        "created_at": exc.created_at,
        # Denormalized bank transaction fields
        "bank_date": bt.transaction_date if bt else None,
        "bank_amount": bt.amount if bt else None,
        "bank_description": bt.description if bt else None,
        "ledger_amount": None,  # populated from ledger entry if matched
    }
    # If the bank transaction has a matched ledger entry, surface its amount
    if bt and bt.ledger_entry:
        data["ledger_amount"] = bt.ledger_entry.amount
    return ExceptionRead.model_validate(data)


@router.get("", response_model=list[ExceptionRead])
async def list_exceptions(
    reconciliation_id: Optional[int] = Query(None),
    status: Optional[ExceptionStatus] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = (
        select(ExceptionModel)
        .options(
            selectinload(ExceptionModel.bank_transaction).selectinload(BankTransaction.ledger_entry)
        )
        .order_by(ExceptionModel.exception_number)
    )
    if reconciliation_id:
        q = q.where(ExceptionModel.reconciliation_id == reconciliation_id)
    if status:
        q = q.where(ExceptionModel.status == status)
    result = await db.execute(q)
    exceptions = result.scalars().all()
    return [_to_read(e) for e in exceptions]


@router.get("/{exception_id}", response_model=ExceptionRead)
async def get_exception(
    exception_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(ExceptionModel)
        .options(
            selectinload(ExceptionModel.bank_transaction).selectinload(BankTransaction.ledger_entry)
        )
        .where(ExceptionModel.id == exception_id)
    )
    exc = result.scalar_one_or_none()
    if not exc:
        raise HTTPException(status_code=404, detail="Exception not found")
    return _to_read(exc)


@router.post("/{exception_id}/review", response_model=ExceptionRead)
async def review_exception(
    exception_id: int,
    payload: ExceptionReview,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Approvers and admins can approve/reject; preparers can edit
    if payload.action in ("approve", "reject") and current_user.role not in (
        UserRole.APPROVER, UserRole.ADMIN
    ):
        raise HTTPException(
            status_code=403, detail="Only approvers can approve or reject exceptions"
        )

    result = await db.execute(
        select(ExceptionModel)
        .options(
            selectinload(ExceptionModel.bank_transaction).selectinload(BankTransaction.ledger_entry)
        )
        .where(ExceptionModel.id == exception_id)
    )
    exc = result.scalar_one_or_none()
    if not exc:
        raise HTTPException(status_code=404, detail="Exception not found")

    now = datetime.now(timezone.utc)

    if payload.action == "approve":
        exc.status = ExceptionStatus.APPROVED
        audit_action = AuditAction.ENTRY_APPROVED
    elif payload.action == "reject":
        exc.status = ExceptionStatus.REJECTED
        audit_action = AuditAction.ENTRY_REJECTED
    elif payload.action == "edit":
        audit_action = AuditAction.ENTRY_EDITED
        if payload.suggested_debit:
            exc.suggested_debit = payload.suggested_debit
        if payload.suggested_credit:
            exc.suggested_credit = payload.suggested_credit
        if payload.suggested_amount:
            exc.suggested_amount = payload.suggested_amount
    else:
        raise HTTPException(status_code=400, detail="Invalid action")

    exc.reviewed_by_id = current_user.id
    exc.reviewed_at = now
    exc.reviewer_note = payload.reviewer_note

    # Append audit log entry with hash chain
    last_log_result = await db.execute(
        select(AuditLog)
        .where(AuditLog.reconciliation_id == exc.reconciliation_id)
        .order_by(AuditLog.id.desc())
        .limit(1)
    )
    last_log = last_log_result.scalar_one_or_none()
    prev_hash = last_log.entry_hash if last_log else None

    details = {
        "exception_id": exc.id,
        "exception_number": exc.exception_number,
        "action": payload.action,
        "reviewer_note": payload.reviewer_note,
    }
    if payload.action == "edit":
        details.update({
            "suggested_debit": exc.suggested_debit,
            "suggested_credit": exc.suggested_credit,
            "suggested_amount": str(exc.suggested_amount) if exc.suggested_amount else None,
        })

    entry_hash = compute_entry_hash(
        action=audit_action.value,
        entity_type="exception",
        entity_id=exc.id,
        user_id=current_user.id,
        details=details,
        created_at=now,
        previous_hash=prev_hash,
    )

    log = AuditLog(
        reconciliation_id=exc.reconciliation_id,
        user_id=current_user.id,
        action=audit_action,
        entity_type="exception",
        entity_id=exc.id,
        details=details,
        previous_hash=prev_hash,
        entry_hash=entry_hash,
        created_at=now,
    )
    db.add(log)
    await db.commit()
    await db.refresh(exc)
    return _to_read(exc)
