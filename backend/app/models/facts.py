from datetime import date, datetime
from decimal import Decimal
import uuid

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class TransactionEvent(Base):
    __tablename__ = "transaction_events"
    __table_args__ = (
        Index("ix_raw_tx_account_eff_date", "account_id", "effective_date"),
        Index("ix_raw_tx_posted_date", "posted_date"),
        Index("ix_raw_tx_advisor_date", "advisor_id", "effective_date"),
        Index("ix_raw_tx_type_date", "event_type", "effective_date"),
        Index("ix_raw_tx_transfer_group", "transfer_group_id"),
        {"schema": "raw"},
    )

    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    external_ref: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("raw.accounts.account_id"), nullable=False
    )
    advisor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("raw.advisors.advisor_id"), nullable=False
    )
    segment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("raw.business_segments.segment_id"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(48), nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    posted_date: Mapped[date] = mapped_column(Date, nullable=False)
    trade_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    security_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("raw.securities.security_id"), nullable=True
    )
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    gross_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    fee_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    net_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    nna_eligible: Mapped[bool] = mapped_column(Boolean, nullable=False)
    external_flow_eligible: Mapped[bool] = mapped_column(Boolean, nullable=False)
    is_internal_transfer: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    counterparty_account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("raw.accounts.account_id"), nullable=True
    )
    transfer_group_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    ingestion_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("raw.ingestion_runs.run_id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class TransactionLeg(Base):
    __tablename__ = "transaction_legs"
    __table_args__ = (
        Index("ix_raw_tx_legs_event", "event_id"),
        Index("ix_raw_tx_legs_account_date", "account_id", "effective_date"),
        Index("ix_raw_tx_legs_transfer_group", "transfer_group_id"),
        {"schema": "raw"},
    )

    leg_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("raw.transaction_events.event_id"), nullable=False
    )
    transfer_group_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("raw.accounts.account_id"), nullable=False
    )
    leg_side: Mapped[str] = mapped_column(String(12), nullable=False)
    asset_or_cash: Mapped[str] = mapped_column(String(12), nullable=False)
    security_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("raw.securities.security_id"), nullable=True
    )
    quantity_delta: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    amount_usd: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    posted_date: Mapped[date] = mapped_column(Date, nullable=False)


class AccountCashBalance(Base):
    __tablename__ = "account_cash_balances"
    __table_args__ = (
        UniqueConstraint("account_id", "as_of_date", name="uq_raw_cash_bal_acct_date"),
        Index("ix_raw_cash_bal_date", "as_of_date"),
        {"schema": "raw"},
    )

    balance_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("raw.accounts.account_id"), nullable=False
    )
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    cash_balance_usd: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    sweep_balance_usd: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)


class PositionSnapshot(Base):
    __tablename__ = "position_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "account_id", "security_id", "as_of_date", name="uq_raw_pos_acct_sec_date"
        ),
        Index("ix_raw_pos_as_of_date", "as_of_date"),
        {"schema": "raw"},
    )

    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("raw.accounts.account_id"), nullable=False
    )
    security_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("raw.securities.security_id"), nullable=False
    )
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    market_price_usd: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    market_value_usd: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    cost_basis_usd: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)


class SecurityPrice(Base):
    __tablename__ = "security_prices"
    __table_args__ = (
        UniqueConstraint("security_id", "price_date", name="uq_raw_sec_price_date"),
        Index("ix_raw_sec_price_date", "price_date"),
        {"schema": "raw"},
    )

    price_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    security_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("raw.securities.security_id"), nullable=False
    )
    price_date: Mapped[date] = mapped_column(Date, nullable=False)
    close_price_usd: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    daily_return: Mapped[Decimal | None] = mapped_column(Numeric(12, 8), nullable=True)


class AccountValuation(Base):
    __tablename__ = "account_valuations"
    __table_args__ = (
        UniqueConstraint("account_id", "as_of_date", name="uq_raw_acct_val_date"),
        Index("ix_raw_acct_val_date_gran", "as_of_date", "period_granularity"),
        Index("ix_raw_acct_val_advisor_date", "advisor_id", "as_of_date"),
        Index("ix_raw_acct_val_segment_date", "segment_id", "as_of_date"),
        {"schema": "raw"},
    )

    valuation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("raw.accounts.account_id"), nullable=False
    )
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    period_granularity: Mapped[str] = mapped_column(String(16), nullable=False)
    cash_value_usd: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    securities_value_usd: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    total_aum_usd: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    advisor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("raw.advisors.advisor_id"), nullable=False
    )
    segment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("raw.business_segments.segment_id"), nullable=False
    )


class ReportedAssetSnapshot(Base):
    """Separate reporting feed table that may contain deliberately injected Story E discrepancies."""

    __tablename__ = "reported_asset_snapshots"
    __table_args__ = (
        Index("ix_raw_reported_date_acct", "as_of_date", "account_id"),
        Index("ix_raw_reported_hash", "record_hash"),
        {"schema": "raw"},
    )

    reported_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    feed_source: Mapped[str] = mapped_column(String(64), nullable=False)
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("raw.accounts.account_id"), nullable=False
    )
    advisor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("raw.advisors.advisor_id"), nullable=False
    )
    segment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("raw.business_segments.segment_id"), nullable=False
    )
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    reported_aum_usd: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    reported_inflows_usd: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    reported_outflows_usd: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    reported_nna_usd: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    reported_market_change_usd: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    reported_fees_usd: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    record_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    is_corrupted_feed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ingestion_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("raw.ingestion_runs.run_id"), nullable=False
    )


class FeeEvent(Base):
    __tablename__ = "fee_events"
    __table_args__ = (
        Index("ix_raw_fee_acct_date", "account_id", "effective_date"),
        {"schema": "raw"},
    )

    fee_event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("raw.transaction_events.event_id"), unique=True, nullable=False
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("raw.accounts.account_id"), nullable=False
    )
    advisor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("raw.advisors.advisor_id"), nullable=False
    )
    fee_type: Mapped[str] = mapped_column(String(32), nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    posted_date: Mapped[date] = mapped_column(Date, nullable=False)
    fee_amount_usd: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)


class IncomeEvent(Base):
    __tablename__ = "income_events"
    __table_args__ = (
        Index("ix_raw_income_acct_date", "account_id", "effective_date"),
        {"schema": "raw"},
    )

    income_event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("raw.transaction_events.event_id"), unique=True, nullable=False
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("raw.accounts.account_id"), nullable=False
    )
    security_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("raw.securities.security_id"), nullable=True
    )
    income_type: Mapped[str] = mapped_column(String(32), nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    posted_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount_usd: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    is_reinvested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
