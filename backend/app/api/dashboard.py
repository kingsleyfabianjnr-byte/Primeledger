"""Dashboard routes."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.reconciliation import (
    Reconciliation, BankAccount, Exception as ExceptionModel,
    ReconciliationStatus, ExceptionStatus, MatchStatus, BankTransaction,
)
from app.schemas.reconciliation import DashboardStats, ReconciliationWithAccount
from sqlalchemy.orm import selectinload

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardStats)
async def get_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Total accounts
    acct_result = await db.execute(
        select(func.count()).select_from(BankAccount).where(BankAccount.is_active == True)
    )
    total_accounts = acct_result.scalar_one()

    # Active reconciliations
    active_result = await db.execute(
        select(func.count())
        .select_from(Reconciliation)
        .where(Reconciliation.status.in_([
            ReconciliationStatus.PENDING,
            ReconciliationStatus.IN_PROGRESS,
            ReconciliationStatus.AWAITING_APPROVAL,
        ]))
    )
    active_reconciliations = active_result.scalar_one()

    # Open exceptions
    exc_result = await db.execute(
        select(func.count())
        .select_from(ExceptionModel)
        .where(ExceptionModel.status == ExceptionStatus.OPEN)
    )
    exceptions_open = exc_result.scalar_one()

    # Matches this month
    match_result = await db.execute(
        select(func.count())
        .select_from(BankTransaction)
        .where(BankTransaction.match_status == MatchStatus.MATCHED)
    )
    matches_this_month = match_result.scalar_one()

    # Total transactions for match rate
    total_txn_result = await db.execute(
        select(func.count()).select_from(BankTransaction)
    )
    total_txn = total_txn_result.scalar_one() or 1
    match_rate = round(matches_this_month / total_txn * 100, 1)

    # Recent reconciliations with account info
    recons_result = await db.execute(
        select(Reconciliation)
        .options(selectinload(Reconciliation.bank_account))
        .order_by(Reconciliation.created_at.desc())
        .limit(10)
    )
    recons = recons_result.scalars().all()

    return DashboardStats(
        total_accounts=total_accounts,
        active_reconciliations=active_reconciliations,
        exceptions_open=exceptions_open,
        matches_this_month=matches_this_month,
        match_rate=match_rate,
        reconciliations=[ReconciliationWithAccount.model_validate(r) for r in recons],
    )
