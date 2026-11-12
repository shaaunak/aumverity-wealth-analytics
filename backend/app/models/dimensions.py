from datetime import date, datetime
from decimal import Decimal
import uuid

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class BusinessSegment(Base):
    __tablename__ = "business_segments"
    __table_args__ = {"schema": "raw"}

    segment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    segment_code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    segment_name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class AssetClass(Base):
    __tablename__ = "asset_classes"
    __table_args__ = {"schema": "raw"}

    asset_class_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    asset_class_code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    asset_class_name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    is_cash: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Security(Base):
    __tablename__ = "securities"
    __table_args__ = (
        Index("ix_raw_securities_asset_class", "asset_class_id"),
        {"schema": "raw"},
    )

    security_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    ticker: Mapped[str] = mapped_column(String(24), unique=True, nullable=False)
    security_name: Mapped[str] = mapped_column(String(160), nullable=False)
    asset_class_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("raw.asset_classes.asset_class_id"), nullable=False
    )
    is_cash_equivalent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    base_price_usd: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    annual_drift: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    annual_vol: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)


class Advisor(Base):
    __tablename__ = "advisors"
    __table_args__ = (
        Index("ix_raw_advisors_segment", "segment_id"),
        {"schema": "raw"},
    )

    advisor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    advisor_code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    segment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("raw.business_segments.segment_id"), nullable=False
    )
    region: Mapped[str] = mapped_column(String(64), nullable=False)
    hire_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ClientHousehold(Base):
    __tablename__ = "client_households"
    __table_args__ = {"schema": "raw"}

    household_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    household_code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    household_name: Mapped[str] = mapped_column(String(160), nullable=False)
    primary_segment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("raw.business_segments.segment_id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Client(Base):
    __tablename__ = "clients"
    __table_args__ = (
        Index("ix_raw_clients_household", "household_id"),
        {"schema": "raw"},
    )

    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    client_code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    household_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("raw.client_households.household_id"), nullable=False
    )
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    client_tier: Mapped[str] = mapped_column(String(32), nullable=False)
    risk_profile: Mapped[str] = mapped_column(String(32), nullable=False)
    onboarding_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = (
        Index("ix_raw_accounts_client", "client_id"),
        Index("ix_raw_accounts_advisor", "advisor_id"),
        Index("ix_raw_accounts_segment", "segment_id"),
        {"schema": "raw"},
    )

    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    account_number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("raw.clients.client_id"), nullable=False
    )
    household_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("raw.client_households.household_id"), nullable=False
    )
    segment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("raw.business_segments.segment_id"), nullable=False
    )
    advisor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("raw.advisors.advisor_id"), nullable=False
    )
    account_type: Mapped[str] = mapped_column(String(48), nullable=False)
    opened_date: Mapped[date] = mapped_column(Date, nullable=False)
    closed_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="OPEN")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AdvisorAssignmentHistory(Base):
    __tablename__ = "advisor_assignment_history"
    __table_args__ = (
        Index("ix_raw_adv_assign_account", "account_id", "effective_from"),
        Index("ix_raw_adv_assign_advisor", "advisor_id", "effective_from"),
        UniqueConstraint(
            "account_id", "effective_from", name="uq_raw_adv_assign_account_eff_from"
        ),
        {"schema": "raw"},
    )

    assignment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("raw.clients.client_id"), nullable=False
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("raw.accounts.account_id"), nullable=False
    )
    advisor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("raw.advisors.advisor_id"), nullable=False
    )
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    assignment_reason: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AccountClassificationHistory(Base):
    __tablename__ = "account_classification_history"
    __table_args__ = (
        Index("ix_raw_acct_class_account", "account_id", "effective_from"),
        UniqueConstraint(
            "account_id", "effective_from", name="uq_raw_acct_class_account_eff_from"
        ),
        {"schema": "raw"},
    )

    classification_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("raw.accounts.account_id"), nullable=False
    )
    segment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("raw.business_segments.segment_id"), nullable=False
    )
    advisor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("raw.advisors.advisor_id"), nullable=False
    )
    account_type: Mapped[str] = mapped_column(String(48), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class CalendarDay(Base):
    __tablename__ = "calendar"
    __table_args__ = {"schema": "raw"}

    calendar_date: Mapped[date] = mapped_column(Date, primary_key=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    quarter: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)
    is_business_day: Mapped[bool] = mapped_column(Boolean, nullable=False)
    is_month_end: Mapped[bool] = mapped_column(Boolean, nullable=False)
    is_quarter_end: Mapped[bool] = mapped_column(Boolean, nullable=False)
    is_90d_window: Mapped[bool] = mapped_column(Boolean, nullable=False)


class ReportingPeriod(Base):
    __tablename__ = "reporting_periods"
    __table_args__ = {"schema": "raw"}

    period_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    period_code: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    period_type: Mapped[str] = mapped_column(String(16), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_closed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
