"""Additive payment records. SaleOrder remains the ONLY authoritative sales ledger."""
from datetime import datetime
from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base
from .models import now


class MerchantBankAccount(Base):
    __tablename__ = "merchant_bank_accounts"
    business_id: Mapped[str] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"), primary_key=True)
    bank_bin: Mapped[str] = mapped_column(String(6), nullable=False)
    account_number: Mapped[str] = mapped_column(String(19), nullable=False)
    account_name: Mapped[str] = mapped_column(String(100), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, onupdate=now)


class POSPaymentIntent(Base):
    __tablename__ = "pos_payment_intents"
    __table_args__ = (
        UniqueConstraint("business_id", "request_id", name="uq_pos_payment_request"),
        UniqueConstraint("reference", name="uq_pos_payment_reference"),
        Index("ix_pos_payment_business_order", "business_id", "order_id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    business_id: Mapped[str] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False)
    branch_id: Mapped[str] = mapped_column(ForeignKey("branches.id"), nullable=False)
    order_id: Mapped[str] = mapped_column(
        ForeignKey("sale_orders.id", ondelete="CASCADE"), nullable=False)
    request_id: Mapped[str] = mapped_column(String(80), nullable=False)
    method: Mapped[str] = mapped_column(String(20), nullable=False)
    reference: Mapped[str] = mapped_column(String(24), nullable=False)
    amount_vnd: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="pending", nullable=False)
    external_transaction_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class POSPaymentEvent(Base):
    __tablename__ = "pos_payment_events"
    __table_args__ = (
        UniqueConstraint("provider", "external_id", name="uq_pos_provider_event"),
        Index("ix_pos_payment_events_tenant", "business_id", "received_at"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    business_id: Mapped[str] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False)
    payment_id: Mapped[str | None] = mapped_column(
        ForeignKey("pos_payment_intents.id"), nullable=True)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    external_id: Mapped[str] = mapped_column(String(100), nullable=False)
    amount_vnd: Mapped[int] = mapped_column(BigInteger, nullable=False)
    outcome: Mapped[str] = mapped_column(String(30), nullable=False)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
