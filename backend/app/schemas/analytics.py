from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import BaseModel

from app.schemas.common import DecimalModel


class PeriodWindow(BaseModel):
    start_date: date
    end_date: date
    period_code: str | None = None


class AppliedFilters(BaseModel):
    start_date: date | None = None
    end_date: date | None = None
    advisor_id: str | None = None
    segment_id: str | None = None
    account_type: str | None = None
    asset_class: str | None = None
    search: str | None = None


class ComponentItem(DecimalModel):
    name: str
    value: Decimal
    share_pct: Decimal | None = None


class DriverItem(DecimalModel):
    entity_id: str | None = None
    label: str
    value: Decimal
    share_pct: Decimal | None = None
    explanation: str


class ReconciliationBadge(DecimalModel):
    status: str
    unexplained_residual_usd: Decimal
    open_issues_count: int


class LineageInfo(BaseModel):
    sql_model: str
    sql_template: str
    source_tables: list[str]
    inclusion_policy: str
    exclusion_policy: str


class ExplainableKPI(DecimalModel):
    metric_id: str
    metric_name: str
    value: Decimal | None
    unit: str = "USD"
    currency: str = "USD"
    data_classification: str = "SYNTHETIC"
    period: PeriodWindow
    filters: AppliedFilters
    formula: str
    definition: str
    components: list[ComponentItem]
    top_drivers: list[DriverItem]
    narrative: str
    reconciliation: ReconciliationBadge
    lineage: LineageInfo
    query_version: str


class MetricSummaryItem(DecimalModel):
    metric_id: str
    metric_name: str
    category: str
    value: Decimal | None
    unit: str
    formula: str
    sql_model: str
    query_version: str


class OverviewResponse(DecimalModel):
    period: PeriodWindow
    filters: AppliedFilters
    query_version: str
    data_classification: str = "SYNTHETIC"
    currency: str = "USD"
    opening_assets_usd: Decimal
    closing_assets_usd: Decimal
    total_asset_growth_usd: Decimal
    total_asset_growth_pct: Decimal | None
    external_net_flows_usd: Decimal
    firm_style_nna_usd: Decimal
    gross_inflows_usd: Decimal
    gross_outflows_usd: Decimal
    market_driven_movement_usd: Decimal
    fees_and_commissions_usd: Decimal
    unexplained_residual_usd: Decimal
    fee_based_assets_usd: Decimal
    reporting_completeness_pct: Decimal | None
    narrative: str


class AssetBridgeStep(DecimalModel):
    step_key: str
    label: str
    amount_usd: Decimal
    step_type: str


class AssetBridgeResponse(DecimalModel):
    period: PeriodWindow
    filters: AppliedFilters
    query_version: str
    steps: list[AssetBridgeStep]
    reconciliation_status: str
    unexplained_residual_usd: Decimal


class AdvisorItem(DecimalModel):
    advisor_id: str
    advisor_code: str
    advisor_name: str
    segment_name: str
    opening_assets_usd: Decimal
    closing_assets_usd: Decimal
    aum_growth_usd: Decimal
    gross_inflows_usd: Decimal
    gross_outflows_usd: Decimal
    external_net_flows_usd: Decimal
    firm_style_nna_usd: Decimal
    market_movement_usd: Decimal
    nna_rank: int
    outflow_rank: int


class ClientItem(DecimalModel):
    client_id: str
    client_code: str
    full_name: str
    client_tier: str
    risk_profile: str
    account_count: int
    total_aum_usd: Decimal


class SegmentItem(DecimalModel):
    segment_id: str
    segment_code: str
    segment_name: str
    opening_assets_usd: Decimal
    closing_assets_usd: Decimal
    total_growth_usd: Decimal
    firm_style_nna_usd: Decimal
    external_net_flows_usd: Decimal
    market_movement_usd: Decimal
    nna_growth_rate_pct: Decimal | None
    segment_aum_share_pct: Decimal | None


class ReconciliationIssueOut(DecimalModel):
    issue_id: str
    issue_code: str
    issue_type: str
    severity: str
    affected_period: str
    affected_scope: str
    expected_amount_usd: Decimal
    reported_amount_usd: Decimal
    difference_usd: Decimal
    likely_reason: str
    detection_rule: str
    status: str
    source_records: list[dict[str, Any]]
    audit_history: list[dict[str, Any]]


class InvestigationRequest(BaseModel):
    template_id: str
    quarter_code: str = "2026-Q3"
    advisor_code: str | None = None
    limit: int = 20


class InvestigationResponse(DecimalModel):
    template_id: str
    title: str
    description: str
    sql_template: str
    query_version: str
    rows: list[dict[str, Any]]
    narrative: str
