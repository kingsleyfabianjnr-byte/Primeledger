"""Contracts API — manage signed contracts, deployed funds, payment schedules."""
from datetime import datetime, timezone, date
from typing import Optional
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from pydantic import BaseModel

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User, UserRole
from app.models.contract import Contract, ContractPayment, ContractStatus, PaymentStatus
from app.models.reconciliation import BankTransaction

router = APIRouter(prefix="/api/contracts", tags=["contracts"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class ContractCreate(BaseModel):
    reference: str
    name: str
    counterparty: str
    bank_account_id: int
    deployed_amount: Decimal
    contract_start: date
    contract_end: Optional[date] = None
    scheduled_payment_amount: Optional[Decimal] = None
    payment_frequency: Optional[str] = None
    currency: str = "USD"
    description: Optional[str] = None


class ContractPaymentRead(BaseModel):
    id: int
    contract_id: int
    bank_transaction_id: Optional[int] = None
    period_month: Optional[date] = None
    expected_amount: Optional[Decimal] = None
    actual_amount: Optional[Decimal] = None
    status: PaymentStatus
    notes: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ContractRead(BaseModel):
    id: int
    reference: str
    name: str
    counterparty: str
    bank_account_id: int
    deployed_amount: Decimal
    used_amount: Decimal
    remaining_balance: Decimal
    utilization_pct: float
    contract_start: date
    contract_end: Optional[date] = None
    scheduled_payment_amount: Optional[Decimal] = None
    payment_frequency: Optional[str] = None
    currency: str
    description: Optional[str] = None
    status: ContractStatus
    is_active: bool
    created_at: datetime
    payments: list[ContractPaymentRead] = []

    model_config = {"from_attributes": True}


class ContractSummary(BaseModel):
    """Lightweight contract card for dashboard/list views."""
    id: int
    reference: str
    name: str
    counterparty: str
    deployed_amount: Decimal
    used_amount: Decimal
    remaining_balance: Decimal
    utilization_pct: float
    status: ContractStatus
    currency: str
    contract_start: date
    contract_end: Optional[date] = None
    scheduled_payment_amount: Optional[Decimal] = None
    payment_frequency: Optional[str] = None
    payment_count: int = 0

    model_config = {"from_attributes": True}


class PaymentMatchRequest(BaseModel):
    bank_transaction_id: int
    actual_amount: Decimal
    notes: Optional[str] = None


# ── Routes ───────────────────────────────────────────────────────────────────

@router.get("", response_model=list[ContractSummary])
async def list_contracts(
    bank_account_id: Optional[int] = Query(None),
    status: Optional[ContractStatus] = Query(None),
    active_only: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = select(Contract).options(selectinload(Contract.payments))
    if bank_account_id:
        q = q.where(Contract.bank_account_id == bank_account_id)
    if status:
        q = q.where(Contract.status == status)
    if active_only:
        q = q.where(Contract.is_active == True)  # noqa: E712
    q = q.order_by(Contract.contract_start.desc())
    result = await db.execute(q)
    contracts = result.scalars().all()
    out = []
    for c in contracts:
        out.append(ContractSummary(
            id=c.id,
            reference=c.reference,
            name=c.name,
            counterparty=c.counterparty,
            deployed_amount=c.deployed_amount,
            used_amount=c.used_amount,
            remaining_balance=c.remaining_balance,
            utilization_pct=c.utilization_pct,
            status=c.status,
            currency=c.currency,
            contract_start=c.contract_start,
            contract_end=c.contract_end,
            scheduled_payment_amount=c.scheduled_payment_amount,
            payment_frequency=c.payment_frequency,
            payment_count=len(c.payments),
        ))
    return out


@router.get("/{contract_id}", response_model=ContractRead)
async def get_contract(
    contract_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Contract)
        .options(selectinload(Contract.payments))
        .where(Contract.id == contract_id)
    )
    contract = result.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    return _to_read(contract)


@router.post("", response_model=ContractRead, status_code=201)
async def create_contract(
    payload: ContractCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in (UserRole.ADMIN, UserRole.PREPARER):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    # Check reference uniqueness
    existing = await db.execute(
        select(Contract).where(Contract.reference == payload.reference)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Contract reference already exists")

    contract = Contract(
        reference=payload.reference,
        name=payload.name,
        counterparty=payload.counterparty,
        bank_account_id=payload.bank_account_id,
        deployed_amount=payload.deployed_amount,
        contract_start=payload.contract_start,
        contract_end=payload.contract_end,
        scheduled_payment_amount=payload.scheduled_payment_amount,
        payment_frequency=payload.payment_frequency,
        currency=payload.currency,
        description=payload.description,
        created_by_id=current_user.id,
    )
    db.add(contract)
    await db.flush()

    # Auto-generate expected payment schedule if frequency + amount set
    if payload.scheduled_payment_amount and payload.payment_frequency == "monthly" and payload.contract_end:
        _generate_monthly_schedule(db, contract)

    await db.commit()
    await db.refresh(contract)
    result = await db.execute(
        select(Contract).options(selectinload(Contract.payments)).where(Contract.id == contract.id)
    )
    return _to_read(result.scalar_one())


@router.patch("/{contract_id}", response_model=ContractRead)
async def update_contract(
    contract_id: int,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in (UserRole.ADMIN, UserRole.PREPARER):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    result = await db.execute(
        select(Contract).options(selectinload(Contract.payments)).where(Contract.id == contract_id)
    )
    contract = result.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")

    allowed = {"name", "description", "contract_end", "status", "is_active",
               "scheduled_payment_amount", "payment_frequency"}
    for k, v in payload.items():
        if k in allowed:
            setattr(contract, k, v)

    await db.commit()
    await db.refresh(contract)
    result = await db.execute(
        select(Contract).options(selectinload(Contract.payments)).where(Contract.id == contract_id)
    )
    return _to_read(result.scalar_one())


@router.post("/{contract_id}/payments/match", response_model=ContractPaymentRead)
async def match_payment(
    contract_id: int,
    payload: PaymentMatchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Match a bank transaction to a contract payment.
    Updates the contract's used_amount and checks for overrun.
    """
    if current_user.role not in (UserRole.ADMIN, UserRole.PREPARER, UserRole.APPROVER):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    result = await db.execute(
        select(Contract).options(selectinload(Contract.payments)).where(Contract.id == contract_id)
    )
    contract = result.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")

    # Verify bank transaction exists
    txn_result = await db.execute(
        select(BankTransaction).where(BankTransaction.id == payload.bank_transaction_id)
    )
    txn = txn_result.scalar_one_or_none()
    if not txn:
        raise HTTPException(status_code=404, detail="Bank transaction not found")

    # Find or create a payment record
    # Look for an EXPECTED payment in the same period
    payment = None
    if txn.transaction_date:
        period = date(txn.transaction_date.year, txn.transaction_date.month, 1)
        for p in contract.payments:
            if p.period_month == period and p.status == PaymentStatus.EXPECTED:
                payment = p
                break

    if payment is None:
        payment = ContractPayment(
            contract_id=contract.id,
            period_month=date(txn.transaction_date.year, txn.transaction_date.month, 1) if txn.transaction_date else None,
        )
        db.add(payment)

    payment.bank_transaction_id = payload.bank_transaction_id
    payment.actual_amount = payload.actual_amount
    payment.notes = payload.notes

    # Determine payment status
    if payment.expected_amount:
        diff = abs(payload.actual_amount - payment.expected_amount)
        pct = diff / payment.expected_amount
        payment.status = PaymentStatus.PARTIAL if pct > Decimal("0.01") else PaymentStatus.MATCHED
    else:
        payment.status = PaymentStatus.MATCHED

    # Update contract used_amount
    contract.used_amount = contract.used_amount + payload.actual_amount

    # Check overrun
    if contract.used_amount > contract.deployed_amount:
        contract.status = ContractStatus.OVERRUN

    # Link transaction to contract
    txn.contract_id = contract.id

    await db.commit()
    await db.refresh(payment)
    return payment


@router.get("/{contract_id}/balance", response_model=dict)
async def get_contract_balance(
    contract_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the running fund balance and payment history for a contract."""
    result = await db.execute(
        select(Contract).options(selectinload(Contract.payments)).where(Contract.id == contract_id)
    )
    contract = result.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")

    matched = [p for p in contract.payments if p.status in (PaymentStatus.MATCHED, PaymentStatus.PARTIAL)]
    expected = [p for p in contract.payments if p.status == PaymentStatus.EXPECTED]
    overdue = [p for p in contract.payments if p.status == PaymentStatus.OVERDUE]

    return {
        "contract_id": contract.id,
        "reference": contract.reference,
        "deployed_amount": str(contract.deployed_amount),
        "used_amount": str(contract.used_amount),
        "remaining_balance": str(contract.remaining_balance),
        "utilization_pct": contract.utilization_pct,
        "status": contract.status,
        "currency": contract.currency,
        "payments_matched": len(matched),
        "payments_expected": len(expected),
        "payments_overdue": len(overdue),
        "is_overrun": contract.used_amount > contract.deployed_amount,
    }


# ── Helpers ──────────────────────────────────────────────────────────────────

def _to_read(c: Contract) -> ContractRead:
    return ContractRead(
        id=c.id,
        reference=c.reference,
        name=c.name,
        counterparty=c.counterparty,
        bank_account_id=c.bank_account_id,
        deployed_amount=c.deployed_amount,
        used_amount=c.used_amount,
        remaining_balance=c.remaining_balance,
        utilization_pct=c.utilization_pct,
        contract_start=c.contract_start,
        contract_end=c.contract_end,
        scheduled_payment_amount=c.scheduled_payment_amount,
        payment_frequency=c.payment_frequency,
        currency=c.currency,
        description=c.description,
        status=c.status,
        is_active=c.is_active,
        created_at=c.created_at,
        payments=[ContractPaymentRead.model_validate(p) for p in (c.payments or [])],
    )


def _generate_monthly_schedule(db: AsyncSession, contract: Contract) -> None:
    """Auto-generate monthly expected payment records from contract_start to contract_end."""
    if not contract.contract_end or not contract.scheduled_payment_amount:
        return
    current = date(contract.contract_start.year, contract.contract_start.month, 1)
    end = date(contract.contract_end.year, contract.contract_end.month, 1)
    while current <= end:
        p = ContractPayment(
            contract_id=contract.id,
            period_month=current,
            expected_amount=contract.scheduled_payment_amount,
            status=PaymentStatus.EXPECTED,
        )
        db.add(p)
        # Advance one month
        if current.month == 12:
            current = date(current.year + 1, 1, 1)
        else:
            current = date(current.year, current.month + 1, 1)
