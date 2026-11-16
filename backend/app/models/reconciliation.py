"""SQLAlchemy models for reconciliation entities."""
from datetime import datetime, timezone, date
from typing import Optional
from decimal import Decimal

from sqlalchemy import (
    String, Boolean, DateTime, Date, Numeric, ForeignKey,
    Text, Enum as SAEnum, Integer, JSON
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.core.database import Base


class ReconciliationStatus(str, enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    REJECTED = "rejected"


class MatchStatus(str, enum.Enum):
    MATCHED = "matched"
    UNMATCHED = "unmatched"
    EXCEPTION = "exception"
    RESOLVED = "resolved"


class ExceptionStatus(str, enum.Enum):
    OPEN = "open"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"


class ExceptionSeverity(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"   # e.g. stale items, overruns


class AuditAction(str, enum.Enum):
    MATCH_CREATED = "match_created"
    EXCEPTION_RAISED = "exception_raised"
    ENTRY_APPROVED = "entry_approved"
    ENTRY_REJECTED = "entry_rejected"
    ENTRY_EDITED = "entry_edited"
    RECONCILIATION_STARTED = "reconciliation_started"
    RECONCILIATION_COMPLETED = "reconciliation_completed"
    USER_LOGGED_IN = "user_logged_in"


class BankAccount(Base):
    __tablename__ = "bank_accounts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    account_number: Mapped[str] = mapped_column(String(50), nullable=False)
    masked_number: Mapped[str] = mapped_column(String(20), nullable=False)
    entity_name: Mapped[str] = mapped_column(String(255), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="USD")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    reconciliations: Mapped[list["Reconciliation"]] = relationship(back_populates="bank_account")


class Reconciliation(Base):
    __tablename__ = "reconciliations"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    bank_account_id: Mapped[int] = mapped_column(ForeignKey("bank_accounts.id"), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[ReconciliationStatus] = mapped_column(
        SAEnum(ReconciliationStatus), default=ReconciliationStatus.PENDING
    )
    total_transactions: Mapped[int] = mapped_column(Integer, default=0)
    matched_count: Mapped[int] = mapped_column(Integer, default=0)
    exception_count: Mapped[int] = mapped_column(Integer, default=0)
    bank_balance: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), nullable=True)
    ledger_balance: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    bank_account: Mapped["BankAccount"] = relationship(back_populates="reconciliations")
    transactions: Mapped[list["BankTransaction"]] = relationship(back_populates="reconciliation")
    exceptions: Mapped[list["Exception"]] = relationship(back_populates="reconciliation")
    audit_logs: Mapped[list["AuditLog"]] = relationship(back_populates="reconciliation")


class BankTransaction(Base):
    __tablename__ = "bank_transactions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    reconciliation_id: Mapped[int] = mapped_column(ForeignKey("reconciliations.id"), nullable=False)
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    reference: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    match_status: Mapped[MatchStatus] = mapped_column(
        SAEnum(MatchStatus), default=MatchStatus.UNMATCHED
    )
    ledger_entry_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("ledger_entries.id"), nullable=True
    )
    confidence_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(4, 2), nullable=True)
    match_method: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    # Contract linkage — set when this transaction is matched to a contract payment
    contract_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("contracts.id"), nullable=True
    )
    # True when the transaction lacks a reference/receipt and needs documentation
    evidence_required: Mapped[bool] = mapped_column(Boolean, default=False)

    reconciliation: Mapped["Reconciliation"] = relationship(back_populates="transactions")
    ledger_entry: Mapped[Optional["LedgerEntry"]] = relationship(foreign_keys=[ledger_entry_id])
    contract: Mapped[Optional["Contract"]] = relationship(  # noqa
        foreign_keys=[contract_id]
    )


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    reconciliation_id: Mapped[int] = mapped_column(ForeignKey("reconciliations.id"), nullable=False)
    entry_date: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    debit_account: Mapped[str] = mapped_column(String(100), nullable=False)
    credit_account: Mapped[str] = mapped_column(String(100), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    reference: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_matched: Mapped[bool] = mapped_column(Boolean, default=False)


class Exception(Base):
    """
    exception_type values:
      timing            — transaction crossed a period boundary
      duplicate         — possible double entry
      missing_entry     — no ledger entry found
      amount_mismatch   — bank vs ledger amount differs
      fx                — foreign currency translation difference
      undocumented_expense — no reference/receipt, requires evidence
      stale_item        — unreconciled for >90 days / prior fiscal year
      contract_variance — payment differs from contracted schedule
    """
    __tablename__ = "exceptions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    reconciliation_id: Mapped[int] = mapped_column(ForeignKey("reconciliations.id"), nullable=False)
    bank_transaction_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("bank_transactions.id"), nullable=True
    )
    exception_number: Mapped[int] = mapped_column(Integer, nullable=False)
    exception_type: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    ai_explanation: Mapped[str] = mapped_column(Text, nullable=False)
    confidence_score: Mapped[Decimal] = mapped_column(Numeric(4, 2), nullable=False)
    suggested_debit: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    suggested_credit: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    suggested_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), nullable=True)
    severity: Mapped[ExceptionSeverity] = mapped_column(
        SAEnum(ExceptionSeverity), default=ExceptionSeverity.MEDIUM
    )
    # How many days this item has been outstanding (populated at exception creation)
    days_outstanding: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # For stale items — the original fiscal year the item belongs to
    original_fiscal_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # For contract_variance — link to the contract
    contract_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("contracts.id"), nullable=True
    )
    status: Mapped[ExceptionStatus] = mapped_column(
        SAEnum(ExceptionStatus), default=ExceptionStatus.OPEN
    )
    reviewed_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewer_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    reconciliation: Mapped["Reconciliation"] = relationship(back_populates="exceptions")
    bank_transaction: Mapped[Optional["BankTransaction"]] = relationship(
        foreign_keys=[bank_transaction_id]
    )
    reviewed_by: Mapped[Optional["User"]] = relationship(foreign_keys=[reviewed_by_id])  # noqa
    contract: Mapped[Optional["Contract"]] = relationship(  # noqa
        foreign_keys=[contract_id]
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    reconciliation_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("reconciliations.id"), nullable=True
    )
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[AuditAction] = mapped_column(SAEnum(AuditAction), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # Hash chain for tamper-evidence
    previous_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    entry_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    reconciliation: Mapped[Optional["Reconciliation"]] = relationship(back_populates="audit_logs")
    user: Mapped[Optional["User"]] = relationship(foreign_keys=[user_id])  # noqa


# Import User here to avoid circular — just for type annotation above
from app.models.user import User  # noqa: E402, F401
from app.models.contract import Contract  # noqa: E402, F401
