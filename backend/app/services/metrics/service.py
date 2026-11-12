from datetime import date
from decimal import ROUND_HALF_UP, Decimal
import math
import uuid

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.schemas.analytics import (
    AdvisorItem,
    AppliedFilters,
    AssetBridgeResponse,
    AssetBridgeStep,
    ClientItem,
    ComponentItem,
    DriverItem,
    ExplainableKPI,
    LineageInfo,
    OverviewResponse,
    PeriodWindow,
    ReconciliationBadge,
    SegmentItem,
)
from app.schemas.common import PaginationMeta
from app.services.lineage import METRIC_REGISTRY

DEFAULT_START = date(2026, 7, 1)
DEFAULT_END = date(2026, 9, 30)
ZERO = Decimal("0.00")


def _q2(val: Decimal | float | int | None) -> Decimal:
    if val is None:
        return ZERO
    return Decimal(str(val)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _validate_uuid(val: str | None, field_name: str) -> str | None:
    if val is None:
        return None
    try:
        return str(uuid.UUID(val))
    except ValueError as exc:
        raise ValueError(f"Invalid UUID for {field_name}: {val}") from exc


def _build_bridge_where(
    start_date: date,
    end_date: date,
    advisor_id: str | None = None,
    segment_id: str | None = None,
    account_type: str | None = None,
) -> tuple[str, dict]:
    clauses = ["b.end_date BETWEEN :start_date AND :end_date"]
    params: dict = {"start_date": start_date, "end_date": end_date}
    if advisor_id:
        clauses.append("b.advisor_id = CAST(:advisor_id AS UUID)")
        params["advisor_id"] = _validate_uuid(advisor_id, "advisor_id")
    if segment_id:
        clauses.append("b.segment_id = CAST(:segment_id AS UUID)")
        params["segment_id"] = _validate_uuid(segment_id, "segment_id")
    if account_type:
        clauses.append("b.account_type = :account_type")
        params["account_type"] = account_type
    return " AND ".join(clauses), params


def get_overview(
    db: Session,
    start_date: date = DEFAULT_START,
    end_date: date = DEFAULT_END,
    advisor_id: str | None = None,
    segment_id: str | None = None,
    account_type: str | None = None,
) -> OverviewResponse:
    settings = get_settings()
    where_sql, params = _build_bridge_where(
        start_date, end_date, advisor_id, segment_id, account_type
    )

    sql = text(
        f"""
        WITH bounds AS (
            SELECT MIN(b.start_date) AS min_start, MAX(b.end_date) AS max_end
            FROM marts.mv_account_monthly_bridge b
            WHERE {where_sql}
        )
        SELECT
            COALESCE(SUM(b.opening_assets_usd) FILTER (WHERE b.start_date = bounds.min_start), 0) AS opening_assets_usd,
            COALESCE(SUM(b.actual_closing_assets_usd) FILTER (WHERE b.end_date = bounds.max_end), 0) AS closing_assets_usd,
            COALESCE(SUM(b.gross_inflows_usd), 0) AS gross_inflows_usd,
            COALESCE(SUM(b.gross_outflows_usd), 0) AS gross_outflows_usd,
            COALESCE(SUM(b.external_net_flows_usd), 0) AS external_net_flows_usd,
            COALESCE(SUM(b.firm_style_nna_usd), 0) AS firm_style_nna_usd,
            COALESCE(SUM(b.price_driven_market_movement_usd), 0) AS market_driven_movement_usd,
            COALESCE(SUM(b.fees_and_commissions_usd), 0) AS fees_and_commissions_usd,
            COALESCE(SUM(b.unexplained_residual_usd), 0) AS unexplained_residual_usd,
            COALESCE(SUM(b.actual_closing_assets_usd) FILTER (
                WHERE b.end_date = bounds.max_end AND b.account_type = 'Fee-based advisory'
            ), 0) AS fee_based_assets_usd
        FROM marts.mv_account_monthly_bridge b
        CROSS JOIN bounds
        WHERE {where_sql}
        """
    )
    row = db.execute(sql, params).mappings().one()

    opening = _q2(row["opening_assets_usd"])
    closing = _q2(row["closing_assets_usd"])
    growth = _q2(closing - opening)
    growth_pct = (
        ((growth / opening) * Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if opening > ZERO
        else None
    )
    nna = _q2(row["firm_style_nna_usd"])
    mkt = _q2(row["market_driven_movement_usd"])
    fees = _q2(row["fees_and_commissions_usd"])
    residual = _q2(row["unexplained_residual_usd"])

    # Reporting completeness at end_date
    comp_row = db.execute(
        text(
            """
            SELECT
                COUNT(*) FILTER (WHERE is_corrupted_feed = FALSE) AS clean_cnt,
                COUNT(*) AS total_cnt
            FROM raw.reported_asset_snapshots
            WHERE as_of_date = :end_date
            """
        ),
        {"end_date": end_date},
    ).mappings().one()
    completeness = None
    if comp_row["total_cnt"] and comp_row["total_cnt"] > 0:
        completeness = (
            Decimal(comp_row["clean_cnt"]) / Decimal(comp_row["total_cnt"]) * Decimal("100")
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    driver_phrase = (
        "both organic Net New Assets and market appreciation"
        if nna > ZERO and mkt > ZERO
        else "market appreciation"
        if mkt > nna
        else "client Net New Assets"
    )
    narrative = (
        f"Total assets moved from ${opening:,.2f} to ${closing:,.2f} ({growth:+,.2f} USD), "
        f"driven by {driver_phrase} (Firm-style NNA: ${nna:,.2f}; Price-driven market movement: "
        f"${mkt:,.2f}; Fees & commissions: -${fees:,.2f})."
    )

    return OverviewResponse(
        period=PeriodWindow(start_date=start_date, end_date=end_date),
        filters=AppliedFilters(
            start_date=start_date,
            end_date=end_date,
            advisor_id=advisor_id,
            segment_id=segment_id,
            account_type=account_type,
        ),
        query_version=settings.CALCULATION_VERSION,
        opening_assets_usd=opening,
        closing_assets_usd=closing,
        total_asset_growth_usd=growth,
        total_asset_growth_pct=growth_pct,
        external_net_flows_usd=_q2(row["external_net_flows_usd"]),
        firm_style_nna_usd=nna,
        gross_inflows_usd=_q2(row["gross_inflows_usd"]),
        gross_outflows_usd=_q2(row["gross_outflows_usd"]),
        market_driven_movement_usd=mkt,
        fees_and_commissions_usd=fees,
        unexplained_residual_usd=residual,
        fee_based_assets_usd=_q2(row["fee_based_assets_usd"]),
        reporting_completeness_pct=completeness,
        narrative=narrative,
    )


def get_asset_bridge(
    db: Session,
    start_date: date = DEFAULT_START,
    end_date: date = DEFAULT_END,
    advisor_id: str | None = None,
    segment_id: str | None = None,
    account_type: str | None = None,
) -> AssetBridgeResponse:
    ov = get_overview(db, start_date, end_date, advisor_id, segment_id, account_type)
    where_sql, params = _build_bridge_where(
        start_date, end_date, advisor_id, segment_id, account_type
    )
    adj_row = db.execute(
        text(
            f"""
            SELECT
                COALESCE(SUM(b.credited_income_usd), 0) AS credited_income_usd,
                COALESCE(SUM(b.explicit_other_adjustments_usd), 0) AS other_adj_usd
            FROM marts.mv_account_monthly_bridge b
            WHERE {where_sql}
            """
        ),
        params,
    ).mappings().one()

    credited_income = _q2(adj_row["credited_income_usd"])
    other_adj = _q2(adj_row["other_adj_usd"])

    steps = [
        AssetBridgeStep(step_key="opening_assets", label="Opening Assets", amount_usd=ov.opening_assets_usd, step_type="BALANCE"),
        AssetBridgeStep(step_key="gross_inflows", label="External Gross Inflows", amount_usd=ov.gross_inflows_usd, step_type="INFLOW"),
        AssetBridgeStep(step_key="gross_outflows", label="External Gross Outflows", amount_usd=-ov.gross_outflows_usd, step_type="OUTFLOW"),
        AssetBridgeStep(step_key="credited_income", label="Credited Interest & Dividends", amount_usd=credited_income, step_type="INFLOW"),
        AssetBridgeStep(step_key="market_movement", label="Price-Driven Market Movement", amount_usd=ov.market_driven_movement_usd, step_type="MARKET"),
        AssetBridgeStep(step_key="fees", label="Fees & Commissions", amount_usd=-ov.fees_and_commissions_usd, step_type="FEE"),
        AssetBridgeStep(step_key="other_adjustments", label="Internal Transfers / Adjustments", amount_usd=other_adj, step_type="ADJUSTMENT"),
        AssetBridgeStep(step_key="unexplained_residual", label="Unexplained Residual", amount_usd=ov.unexplained_residual_usd, step_type="RESIDUAL"),
        AssetBridgeStep(step_key="closing_assets", label="Actual Closing Assets", amount_usd=ov.closing_assets_usd, step_type="BALANCE"),
    ]
    recon_status = "RECONCILED" if abs(ov.unexplained_residual_usd) < Decimal("1.00") else "VARIANCE_DETECTED"
    return AssetBridgeResponse(
        period=ov.period,
        filters=ov.filters,
        query_version=ov.query_version,
        steps=steps,
        reconciliation_status=recon_status,
        unexplained_residual_usd=ov.unexplained_residual_usd,
    )


def get_explainable_metric(
    db: Session,
    metric_id: str,
    start_date: date = DEFAULT_START,
    end_date: date = DEFAULT_END,
    advisor_id: str | None = None,
    segment_id: str | None = None,
    account_type: str | None = None,
) -> ExplainableKPI:
    if metric_id not in METRIC_REGISTRY:
        raise KeyError(f"Unknown metric_id: {metric_id}")

    spec = METRIC_REGISTRY[metric_id]
    ov = get_overview(db, start_date, end_date, advisor_id, segment_id, account_type)

    value_map: dict[str, Decimal | None] = {
        "opening_assets": ov.opening_assets_usd,
        "closing_assets": ov.closing_assets_usd,
        "total_asset_growth": ov.total_asset_growth_usd,
        "external_net_flows": ov.external_net_flows_usd,
        "firm_style_nna": ov.firm_style_nna_usd,
        "gross_inflows": ov.gross_inflows_usd,
        "gross_outflows": ov.gross_outflows_usd,
        "market_driven_movement": ov.market_driven_movement_usd,
        "fees_and_commissions": ov.fees_and_commissions_usd,
        "fee_based_assets": ov.fee_based_assets_usd,
        "fee_based_asset_flows": ov.firm_style_nna_usd,
        "period_nna_growth_rate": (
            ((ov.firm_style_nna_usd / ov.opening_assets_usd) * Decimal("100")).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            if ov.opening_assets_usd > ZERO
            else None
        ),
        "reconciliation_residual": ov.unexplained_residual_usd,
        "reporting_completeness": ov.reporting_completeness_pct,
        "estimated_fee_revenue_proxy": _q2(ov.fee_based_assets_usd * Decimal("0.0085")),
    }
    val = value_map.get(metric_id)

    # Top segment drivers from SQL
    seg_rows = db.execute(
        text(
            """
            SELECT
                bs.segment_id::TEXT AS entity_id,
                bs.segment_name AS label,
                COALESCE(SUM(b.firm_style_nna_usd), 0) AS nna_usd,
                COALESCE(SUM(b.price_driven_market_movement_usd), 0) AS mkt_usd,
                COALESCE(SUM(b.actual_closing_assets_usd) FILTER (WHERE b.end_date = :end_date), 0) AS closing_usd
            FROM marts.mv_account_monthly_bridge b
            JOIN raw.business_segments bs ON bs.segment_id = b.segment_id
            WHERE b.end_date BETWEEN :start_date AND :end_date
            GROUP BY bs.segment_id, bs.segment_name
            ORDER BY ABS(SUM(b.firm_style_nna_usd)) DESC
            """
        ),
        {"start_date": start_date, "end_date": end_date},
    ).mappings().all()

    drivers: list[DriverItem] = []
    total_abs = sum((abs(_q2(r["nna_usd"])) for r in seg_rows), ZERO)
    for r in seg_rows:
        d_val = _q2(r["mkt_usd"]) if metric_id == "market_driven_movement" else _q2(r["nna_usd"])
        share = (
            ((abs(_q2(r["nna_usd"])) / total_abs) * Decimal("100")).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            if total_abs > ZERO
            else None
        )
        drivers.append(
            DriverItem(
                entity_id=r["entity_id"],
                label=r["label"],
                value=d_val,
                share_pct=share,
                explanation=f"{r['label']} contributed ${d_val:,.2f} during {start_date} to {end_date}.",
            )
        )

    components = [
        ComponentItem(name="Gross Inflows", value=ov.gross_inflows_usd),
        ComponentItem(name="Gross Outflows", value=-ov.gross_outflows_usd),
        ComponentItem(name="Market Movement", value=ov.market_driven_movement_usd),
        ComponentItem(name="Fees & Commissions", value=-ov.fees_and_commissions_usd),
    ]

    top_seg = drivers[0].label if drivers else "all segments"
    narrative = (
        f"{spec.metric_name} measured {val if val is not None else 'NULL'} {spec.unit} "
        f"for {start_date} to {end_date}. Most activity was concentrated in {top_seg}."
    )

    open_issues = db.execute(
        text("SELECT COUNT(*) FROM raw.reported_asset_snapshots WHERE is_corrupted_feed = TRUE")
    ).scalar_one()

    return ExplainableKPI(
        metric_id=spec.metric_id,
        metric_name=spec.metric_name,
        value=val,
        unit=spec.unit,
        period=ov.period,
        filters=ov.filters,
        formula=spec.formula,
        definition=spec.definition,
        components=components,
        top_drivers=drivers,
        narrative=narrative,
        reconciliation=ReconciliationBadge(
            status="RECONCILED" if abs(ov.unexplained_residual_usd) < Decimal("1.00") else "VARIANCE_DETECTED",
            unexplained_residual_usd=ov.unexplained_residual_usd,
            open_issues_count=int(open_issues),
        ),
        lineage=LineageInfo(
            sql_model=spec.sql_model,
            sql_template=spec.sql_template,
            source_tables=spec.source_tables,
            inclusion_policy=spec.inclusion_policy,
            exclusion_policy=spec.exclusion_policy,
        ),
        query_version=ov.query_version,
    )


def list_advisors(
    db: Session,
    quarter_code: str = "2026-Q3",
    segment_id: str | None = None,
    search: str | None = None,
    sort_by: str = "firm_style_nna_usd",
    sort_dir: str = "desc",
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[AdvisorItem], PaginationMeta]:
    allowed_sorts = {
        "firm_style_nna_usd": "aqp.firm_style_nna_usd",
        "external_net_flows_usd": "aqp.external_net_flows_usd",
        "closing_assets_usd": "aqp.closing_assets_usd",
        "aum_growth_usd": "aqp.aum_growth_usd",
        "advisor_code": "aqp.advisor_code",
    }
    sort_col = allowed_sorts.get(sort_by, "aqp.firm_style_nna_usd")
    direction = "ASC" if sort_dir.lower() == "asc" else "DESC"

    clauses = ["aqp.quarter_code = :quarter_code"]
    params: dict = {"quarter_code": quarter_code}
    if segment_id:
        clauses.append("a.segment_id = CAST(:segment_id AS UUID)")
        params["segment_id"] = _validate_uuid(segment_id, "segment_id")
    if search:
        clauses.append("(aqp.advisor_code ILIKE :search OR aqp.advisor_name ILIKE :search)")
        params["search"] = f"%{search}%"

    where_sql = " AND ".join(clauses)
    total = db.execute(
        text(
            f"""
            SELECT COUNT(*)
            FROM marts.advisor_quarterly_performance aqp
            JOIN raw.advisors a ON a.advisor_id = aqp.advisor_id
            WHERE {where_sql}
            """
        ),
        params,
    ).scalar_one()

    offset = (page - 1) * page_size
    params["limit"] = page_size
    params["offset"] = offset

    rows = db.execute(
        text(
            f"""
            SELECT
                aqp.advisor_id::TEXT,
                aqp.advisor_code,
                aqp.advisor_name,
                aqp.segment_name,
                aqp.opening_assets_usd,
                aqp.closing_assets_usd,
                aqp.aum_growth_usd,
                aqp.gross_inflows_usd,
                aqp.gross_outflows_usd,
                aqp.external_net_flows_usd,
                aqp.firm_style_nna_usd,
                aqp.market_movement_usd,
                aqp.nna_rank,
                aqp.outflow_rank
            FROM marts.advisor_quarterly_performance aqp
            JOIN raw.advisors a ON a.advisor_id = aqp.advisor_id
            WHERE {where_sql}
            ORDER BY {sort_col} {direction}
            LIMIT :limit OFFSET :offset
            """
        ),
        params,
    ).mappings().all()

    items = [AdvisorItem(**dict(r)) for r in rows]
    meta = PaginationMeta(
        page=page,
        page_size=page_size,
        total_items=int(total),
        total_pages=max(1, math.ceil(int(total) / page_size)),
    )
    return items, meta


def list_segments(db: Session, quarter_code: str = "2026-Q3") -> list[SegmentItem]:
    rows = db.execute(
        text(
            """
            SELECT
                segment_id::TEXT,
                segment_code,
                segment_name,
                opening_assets_usd,
                closing_assets_usd,
                total_growth_usd,
                firm_style_nna_usd,
                external_net_flows_usd,
                market_movement_usd,
                nna_growth_rate_pct,
                segment_aum_share_pct
            FROM marts.segment_quarterly_contribution
            WHERE quarter_code = :quarter_code
            ORDER BY closing_assets_usd DESC
            """
        ),
        {"quarter_code": quarter_code},
    ).mappings().all()
    return [SegmentItem(**dict(r)) for r in rows]


def list_clients(
    db: Session,
    search: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[ClientItem], PaginationMeta]:
    clauses = ["1=1"]
    params: dict = {}
    if search:
        clauses.append("(c.client_code ILIKE :search OR c.full_name ILIKE :search)")
        params["search"] = f"%{search}%"
    where_sql = " AND ".join(clauses)

    total = db.execute(
        text(f"SELECT COUNT(*) FROM raw.clients c WHERE {where_sql}"), params
    ).scalar_one()

    params["limit"] = page_size
    params["offset"] = (page - 1) * page_size

    rows = db.execute(
        text(
            f"""
            SELECT
                c.client_id::TEXT,
                c.client_code,
                c.full_name,
                c.client_tier,
                c.risk_profile,
                COUNT(DISTINCT a.account_id) AS account_count,
                COALESCE(SUM(av.total_aum_usd), 0)::NUMERIC(18, 2) AS total_aum_usd
            FROM raw.clients c
            LEFT JOIN raw.accounts a ON a.client_id = c.client_id
            LEFT JOIN raw.account_valuations av
                ON av.account_id = a.account_id AND av.as_of_date = '2026-09-30'
            WHERE {where_sql}
            GROUP BY c.client_id, c.client_code, c.full_name, c.client_tier, c.risk_profile
            ORDER BY total_aum_usd DESC
            LIMIT :limit OFFSET :offset
            """
        ),
        params,
    ).mappings().all()

    items = [ClientItem(**dict(r)) for r in rows]
    meta = PaginationMeta(
        page=page,
        page_size=page_size,
        total_items=int(total),
        total_pages=max(1, math.ceil(int(total) / page_size)),
    )
    return items, meta
