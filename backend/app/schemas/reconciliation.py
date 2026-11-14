"""Pydantic schemas for reconciliation."""
from datetime import datetime, date
from typing import Optional, List
from decimal import Decimal

from pydantic import BaseModel

from app.models.reconciliation import (
    ReconciliationStatus, MatchStatus, ExceptionStatus, AuditAction
)


# ── BankAccount ──────────────────────────────────────────────────────────────

class BankAccountBase(BaseModel):
    name: str
    account_number: str
    masked_number: str
    entity_name: str
    currency: str = "USD"


class BankAccountCreate(BankAccountBase):
    pass


class BankAccountRead(BankAccountBase):
    id: int
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Reconciliation ────────────────────────────────────────────────────────────

class ReconciliationCreate(BaseModel):
    bank_account_id: int
    period_start: date
    period_end: date


class ReconciliationRead(BaseModel):
    id: int
    bank_account_id: int
    period_start: date
    period_end: date
    status: ReconciliationStatus
    total_transactions: int
    matched_count: int
    exception_count: int
    bank_balance: Optional[Decimal] = None
    ledger_balance: Optional[Decimal] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ReconciliationWithAccount(ReconciliationRead):
    bank_account: BankAccountRead


# ── Exception ─────────────────────────────────────────────────────────────────

class ExceptionBase(BaseModel):
    exception_type: str
    description: str
    ai_explanation: str
    confidence_score: Decimal
    suggested_debit: Optional[str] = None
    suggested_credit: Optional[str] = None
    suggested_amount: Optional[Decimal] = None


class ExceptionRead(ExceptionBase):
    id: int
    reconciliation_id: int
    bank_transaction_id: Optional[int] = None
    exception_number: int
    status: ExceptionStatus
    reviewed_by_id: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    reviewer_note: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ExceptionReview(BaseModel):
    action: str  # "approve" | "reject" | "edit"
    reviewer_note: Optional[str] = None
    # Allow editing the suggested journal entry
    suggested_debit: Optional[str] = None
    suggested_credit: Optional[str] = None
    suggested_amount: Optional[Decimal] = None


# ── AuditLog ──────────────────────────────────────────────────────────────────

class AuditLogRead(BaseModel):
    id: int
    reconciliation_id: Optional[int] = None
    user_id: Optional[int] = None
    action: AuditAction
    entity_type: str
    entity_id: Optional[int] = None
    details: Optional[dict] = None
    previous_hash: Optional[str] = None
    entry_hash: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Dashboard ─────────────────────────────────────────────────────────────────

class DashboardStats(BaseModel):
    total_accounts: int
    active_reconciliations: int
    exceptions_open: int
    matches_this_month: int
    match_rate: float  # percentage
    reconciliations: List[ReconciliationWithAccount]
