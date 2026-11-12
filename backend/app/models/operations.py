from datetime import date, datetime
from decimal import Decimal
import uuid

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"
    __table_args__ = {"schema": "raw"}

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    profile: Mapped[str] = mapped_column(String(24), nullable=False)
    seed: Mapped[int] = mapped_column(Integer, nullable=False)
    baseline_date: Mapped[date] = mapped_column(Date, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    row_counts_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    manifest_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class ValidationResult(Base):
    __tablename__ = "validation_results"
    __table_args__ = (
        Index("ix_raw_val_run", "run_id"),
        {"schema": "raw"},
    )

    validation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("raw.ingestion_runs.run_id"), nullable=False
    )
    check_name: Mapped[str] = mapped_column(String(120), nullable=False)
    layer: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    details_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ReconciliationIssue(Base):
    __tablename__ = "reconciliation_issues"
    __table_args__ = (
        Index("ix_raw_recon_run_type", "run_id", "issue_type"),
        {"schema": "raw"},
    )

    issue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("raw.ingestion_runs.run_id"), nullable=False
    )
    issue_code: Mapped[str] = mapped_column(String(64), nullable=False)
    issue_type: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    affected_period: Mapped[str] = mapped_column(String(32), nullable=False)
    account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("raw.accounts.account_id"), nullable=True
    )
    advisor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("raw.advisors.advisor_id"), nullable=True
    )
    expected_value_usd: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    reported_value_usd: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    variance_usd: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    detection_sql: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="OPEN")
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class MetricDefinition(Base):
    __tablename__ = "metric_definitions"
    __table_args__ = {"schema": "raw"}

    metric_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    metric_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    metric_name: Mapped[str] = mapped_column(String(120), nullable=False)
    formula_text: Mapped[str] = mapped_column(Text, nullable=False)
    sql_source: Mapped[str] = mapped_column(String(160), nullable=False)
    owner: Mapped[str] = mapped_column(String(64), nullable=False)
    calculation_version: Mapped[str] = mapped_column(String(24), nullable=False)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_raw_audit_entity", "entity_type", "entity_id"),
        {"schema": "raw"},
    )

    audit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("raw.ingestion_runs.run_id"), nullable=True
    )
    actor: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
