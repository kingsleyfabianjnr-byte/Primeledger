"""Contract models — tracks signed contracts, deployed funds, payment schedules."""
from datetime import datetime, timezone, date
from typing import Optional
from decimal import Decimal
import enum

from sqlalchemy import (
    String, Boolean, DateTime, Date, Numeric, ForeignKey,
    Text, Enum as SAEnum, Integer
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ContractStatus(str, enum.Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    SUSPENDED = "suspended"
    OVERRUN = "overrun"      # payments exceeded deployed funds


class PaymentStatus(str, enum.Enum):
    EXPECTED = "expected"
    MATCHED = "matched"      # reconciled to a bank transaction
    OVERDUE = "overdue"
    PARTIAL = "partial"


class Contract(Base):
    """
    Represents a signed contract with an initial fund deployment.

    The reconciliation engine verifies that:
      - Every contract payment transaction reduces the running balance
      - Payments match the agreed schedule (amount + period)
      - Total payments never exceed deployed_amount (overrun detection)
      - Unmatched payments generate exceptions
    """
    __tablename__ = "contracts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    reference: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    # e.g. "CNT-2024-001"
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    counterparty: Mapped[str] = mapped_column(String(255), nullable=False)
    bank_account_id: Mapped[int] = mapped_column(ForeignKey("bank_accounts.id"), nullable=False)

    # Fund deployment
    deployed_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    # Total payments made against this contract (updated on each reconciled payment)
    used_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0.00"))

    # Schedule
    contract_start: Mapped[date] = mapped_column(Date, nullable=False)
    contract_end: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    scheduled_payment_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), nullable=True)
    # e.g. "monthly", "quarterly", "milestone"
    payment_frequency: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="USD")

    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[ContractStatus] = mapped_column(
        SAEnum(ContractStatus), default=ContractStatus.ACTIVE
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    bank_account: Mapped["BankAccount"] = relationship(foreign_keys=[bank_account_id])  # noqa
    payments: Mapped[list["ContractPayment"]] = relationship(back_populates="contract")
    created_by: Mapped[Optional["User"]] = relationship(foreign_keys=[created_by_id])  # noqa

    @property
    def remaining_balance(self) -> Decimal:
        return self.deployed_amount - self.used_amount

    @property
    def utilization_pct(self) -> float:
        if self.deployed_amount == 0:
            return 0.0
        return float(self.used_amount / self.deployed_amount * 100)


class ContractPayment(Base):
    """
    An individual payment against a contract — either expected (from schedule)
    or observed (from bank statement), linked after reconciliation.
    """
    __tablename__ = "contract_payments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("contracts.id"), nullable=False)
    # If linked to a bank transaction after matching
    bank_transaction_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("bank_transactions.id"), nullable=True
    )
    period_month: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    # First day of the payment period
    expected_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), nullable=True)
    actual_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), nullable=True)
    status: Mapped[PaymentStatus] = mapped_column(
        SAEnum(PaymentStatus), default=PaymentStatus.EXPECTED
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    contract: Mapped["Contract"] = relationship(back_populates="payments")
    bank_transaction: Mapped[Optional["BankTransaction"]] = relationship(  # noqa
        foreign_keys=[bank_transaction_id]
    )


# Avoid circular imports
from app.models.reconciliation import BankAccount, BankTransaction  # noqa: E402, F401
from app.models.user import User  # noqa: E402, F401
