"""Reconciliation CRUD routes."""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.reconciliation import (
    Reconciliation, ReconciliationStatus, AuditLog, AuditAction,
    BankAccount,
)
from app.schemas.reconciliation import (
    ReconciliationCreate, ReconciliationRead, ReconciliationWithAccount
)
from app.services.ai_pipeline import compute_entry_hash

router = APIRouter(prefix="/api/reconciliations", tags=["reconciliations"])


@router.get("", response_model=list[ReconciliationWithAccount])
async def list_reconciliations(
    account_id: Optional[int] = Query(None),
    status: Optional[ReconciliationStatus] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = (
        select(Reconciliation)
        .options(selectinload(Reconciliation.bank_account))
        .order_by(Reconciliation.created_at.desc())
    )
    if account_id:
        q = q.where(Reconciliation.bank_account_id == account_id)
    if status:
        q = q.where(Reconciliation.status == status)
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/{recon_id}", response_model=ReconciliationWithAccount)
async def get_reconciliation(
    recon_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Reconciliation)
        .options(selectinload(Reconciliation.bank_account))
        .where(Reconciliation.id == recon_id)
    )
    recon = result.scalar_one_or_none()
    if not recon:
        raise HTTPException(status_code=404, detail="Reconciliation not found")
    return recon


@router.post("", response_model=ReconciliationRead, status_code=201)
async def create_reconciliation(
    payload: ReconciliationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Verify bank account exists
    acct = await db.get(BankAccount, payload.bank_account_id)
    if not acct:
        raise HTTPException(status_code=404, detail="Bank account not found")

    recon = Reconciliation(
        bank_account_id=payload.bank_account_id,
        period_start=payload.period_start,
        period_end=payload.period_end,
        status=ReconciliationStatus.PENDING,
        created_by_id=current_user.id,
    )
    db.add(recon)
    await db.flush()

    now = datetime.now(timezone.utc)
    entry_hash = compute_entry_hash(
        action=AuditAction.RECONCILIATION_STARTED.value,
        entity_type="reconciliation",
        entity_id=recon.id,
        user_id=current_user.id,
        details={"period_start": str(payload.period_start), "period_end": str(payload.period_end)},
        created_at=now,
        previous_hash=None,
    )
    log = AuditLog(
        reconciliation_id=recon.id,
        user_id=current_user.id,
        action=AuditAction.RECONCILIATION_STARTED,
        entity_type="reconciliation",
        entity_id=recon.id,
        details={"period_start": str(payload.period_start), "period_end": str(payload.period_end)},
        previous_hash=None,
        entry_hash=entry_hash,
        created_at=now,
    )
    db.add(log)
    await db.commit()
    await db.refresh(recon)
    return recon
