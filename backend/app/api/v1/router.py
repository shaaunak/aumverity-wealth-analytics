from datetime import date
import math
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.routes.health import health_check, readiness_check
from app.core.config import get_settings
from app.db.session import get_db
from app.schemas.analytics import (
    AdvisorItem,
    AssetBridgeResponse,
    ClientItem,
    ExplainableKPI,
    InvestigationRequest,
    InvestigationResponse,
    LineageInfo,
    MetricSummaryItem,
    OverviewResponse,
    ReconciliationIssueOut,
    SegmentItem,
)
from app.schemas.common import PaginatedResponse, PaginationMeta
from app.services.exports.excel_service import generate_quarterly_excel
from app.services.exports.tableau_service import generate_tableau_csv
from app.services.investigations.service import (
    TEMPLATES,
    list_saved_investigations,
    parse_constrained_intent,
    run_investigation,
    save_investigation_record,
)
from app.services.lineage import METRIC_REGISTRY
from app.services.metrics.service import (
    DEFAULT_END,
    DEFAULT_START,
    get_asset_bridge,
    get_explainable_metric,
    get_overview,
    list_advisors,
    list_clients,
    list_segments,
)
from app.services.reconciliation.service import (
    acknowledge_issue_demo,
    discover_reconciliation_issues,
)

router = APIRouter(prefix="/api/v1", tags=["v1"])

# System probes under /api/v1 as well as root
router.add_api_route("/health", health_check, methods=["GET"], tags=["system"])
router.add_api_route("/ready", readiness_check, methods=["GET"], tags=["system"])


def _validate_uuid_or_422(val: str, name: str) -> str:
    try:
        return str(uuid.UUID(val))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid UUID for {name}",
        ) from exc


@router.get("/overview", response_model=OverviewResponse)
def api_overview(
    start_date: date = Query(DEFAULT_START),
    end_date: date = Query(DEFAULT_END),
    advisor_id: str | None = Query(None),
    segment_id: str | None = Query(None),
    account_type: str | None = Query(None),
    db: Session = Depends(get_db),
):
    if start_date > end_date:
        raise HTTPException(status_code=422, detail="start_date must be <= end_date")
    try:
        return get_overview(db, start_date, end_date, advisor_id, segment_id, account_type)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/metrics", response_model=list[MetricSummaryItem])
def api_list_metrics(
    start_date: date = Query(DEFAULT_START),
    end_date: date = Query(DEFAULT_END),
    db: Session = Depends(get_db),
):
    settings = get_settings()
    ov = get_overview(db, start_date, end_date)
    vals = {
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
        "reconciliation_residual": ov.unexplained_residual_usd,
        "reporting_completeness": ov.reporting_completeness_pct,
    }
    return [
        MetricSummaryItem(
            metric_id=spec.metric_id,
            metric_name=spec.metric_name,
            category=spec.category,
            value=vals.get(spec.metric_id),
            unit=spec.unit,
            formula=spec.formula,
            sql_model=spec.sql_model,
            query_version=settings.CALCULATION_VERSION,
        )
        for spec in METRIC_REGISTRY.values()
    ]


@router.get("/metrics/{metric_id}", response_model=ExplainableKPI)
def api_get_metric(
    metric_id: str,
    start_date: date = Query(DEFAULT_START),
    end_date: date = Query(DEFAULT_END),
    advisor_id: str | None = Query(None),
    segment_id: str | None = Query(None),
    account_type: str | None = Query(None),
    db: Session = Depends(get_db),
):
    try:
        return get_explainable_metric(
            db, metric_id, start_date, end_date, advisor_id, segment_id, account_type
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/metrics/{metric_id}/lineage", response_model=LineageInfo)
def api_get_metric_lineage(metric_id: str):
    if metric_id not in METRIC_REGISTRY:
        raise HTTPException(status_code=404, detail=f"Unknown metric_id: {metric_id}")
    spec = METRIC_REGISTRY[metric_id]
    return LineageInfo(
        sql_model=spec.sql_model,
        sql_template=spec.sql_template,
        source_tables=spec.source_tables,
        inclusion_policy=spec.inclusion_policy,
        exclusion_policy=spec.exclusion_policy,
    )


@router.get("/metrics/{metric_id}/evidence")
def api_get_metric_evidence(
    metric_id: str,
    start_date: date = Query(DEFAULT_START),
    end_date: date = Query(DEFAULT_END),
    segment_id: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
):
    if metric_id not in METRIC_REGISTRY:
        raise HTTPException(status_code=404, detail=f"Unknown metric_id: {metric_id}")
    clauses = ["t.effective_date BETWEEN :start_date AND :end_date"]
    params: dict = {"start_date": start_date, "end_date": end_date}
    if segment_id:
        clauses.append("t.segment_id = CAST(:segment_id AS UUID)")
        params["segment_id"] = _validate_uuid_or_422(segment_id, "segment_id")
    if metric_id == "firm_style_nna":
        clauses.append("t.nna_eligible = TRUE")
    elif metric_id == "external_net_flows":
        clauses.append("t.external_flow_eligible = TRUE")
    elif metric_id == "fees_and_commissions":
        clauses.append("(t.fee_amount > 0 OR t.event_type IN ('MANAGEMENT_FEE', 'COMMISSION'))")
    where_sql = " AND ".join(clauses)

    total = db.execute(
        text(f"SELECT COUNT(*) FROM staging.stg_transactions t WHERE {where_sql}"), params
    ).scalar_one()
    params["limit"] = page_size
    params["offset"] = (page - 1) * page_size
    rows = db.execute(
        text(
            f"""
            SELECT t.event_id::TEXT, t.external_ref, acct.account_number,
                   t.effective_date, t.posted_date, t.event_type, t.flow_classification,
                   t.gross_amount, t.fee_amount, t.net_amount
            FROM staging.stg_transactions t
            JOIN raw.accounts acct ON acct.account_id = t.account_id
            WHERE {where_sql}
            ORDER BY ABS(t.net_amount) DESC, t.effective_date DESC
            LIMIT :limit OFFSET :offset
            """
        ),
        params,
    ).mappings().all()
    return {
        "items": [dict(r) for r in rows],
        "pagination": PaginationMeta(
            page=page,
            page_size=page_size,
            total_items=int(total),
            total_pages=max(1, math.ceil(int(total) / page_size)),
        ),
    }


@router.get("/metric-dictionary")
def api_metric_dictionary():
    return [
        {
            "metric_id": s.metric_id,
            "metric_name": s.metric_name,
            "category": s.category,
            "unit": s.unit,
            "formula": s.formula,
            "definition": s.definition,
            "sql_model": s.sql_model,
            "sql_template": s.sql_template,
            "source_tables": s.source_tables,
            "inclusion_policy": s.inclusion_policy,
            "exclusion_policy": s.exclusion_policy,
        }
        for s in METRIC_REGISTRY.values()
    ]


@router.get("/asset-bridge", response_model=AssetBridgeResponse)
def api_asset_bridge(
    start_date: date = Query(DEFAULT_START),
    end_date: date = Query(DEFAULT_END),
    advisor_id: str | None = Query(None),
    segment_id: str | None = Query(None),
    account_type: str | None = Query(None),
    db: Session = Depends(get_db),
):
    try:
        return get_asset_bridge(db, start_date, end_date, advisor_id, segment_id, account_type)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/advisors", response_model=PaginatedResponse[AdvisorItem])
def api_list_advisors(
    quarter_code: str = Query("2026-Q3"),
    segment_id: str | None = Query(None),
    search: str | None = Query(None),
    sort_by: str = Query("firm_style_nna_usd"),
    sort_dir: str = Query("desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    try:
        items, meta = list_advisors(
            db, quarter_code, segment_id, search, sort_by, sort_dir, page, page_size
        )
        return PaginatedResponse(items=items, pagination=meta)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/advisors/{advisor_id}", response_model=AdvisorItem)
def api_get_advisor(
    advisor_id: str,
    quarter_code: str = Query("2026-Q3"),
    db: Session = Depends(get_db),
):
    adv_uuid = _validate_uuid_or_422(advisor_id, "advisor_id")
    row = db.execute(
        text(
            """
            SELECT
                advisor_id::TEXT, advisor_code, advisor_name, segment_name,
                opening_assets_usd, closing_assets_usd, aum_growth_usd,
                gross_inflows_usd, gross_outflows_usd, external_net_flows_usd,
                firm_style_nna_usd, market_movement_usd, nna_rank, outflow_rank
            FROM marts.advisor_quarterly_performance
            WHERE advisor_id = CAST(:advisor_id AS UUID) AND quarter_code = :quarter_code
            """
        ),
        {"advisor_id": adv_uuid, "quarter_code": quarter_code},
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Advisor not found for quarter")
    return AdvisorItem(**dict(row))


@router.get("/advisors/{advisor_id}/flows")
def api_get_advisor_flows(advisor_id: str, db: Session = Depends(get_db)):
    adv_uuid = _validate_uuid_or_422(advisor_id, "advisor_id")
    rows = db.execute(
        text(
            """
            SELECT period_code, start_date, end_date,
                   external_inflows_usd, external_outflows_usd,
                   external_net_flows_usd, firm_style_nna_usd, internal_transfer_net_usd
            FROM marts.advisor_level_flows
            WHERE advisor_id = CAST(:advisor_id AS UUID)
            ORDER BY start_date
            """
        ),
        {"advisor_id": adv_uuid},
    ).mappings().all()
    return [dict(r) for r in rows]


@router.get("/advisors/{advisor_id}/clients")
def api_get_advisor_clients(advisor_id: str, db: Session = Depends(get_db)):
    adv_uuid = _validate_uuid_or_422(advisor_id, "advisor_id")
    rows = db.execute(
        text(
            """
            SELECT
                c.client_id::TEXT, c.client_code, c.full_name, c.client_tier,
                COUNT(DISTINCT a.account_id) AS account_count,
                COALESCE(SUM(av.total_aum_usd), 0)::NUMERIC(18, 2) AS total_aum_usd
            FROM raw.accounts a
            JOIN raw.clients c ON c.client_id = a.client_id
            LEFT JOIN raw.account_valuations av
                ON av.account_id = a.account_id AND av.as_of_date = '2026-09-30'
            WHERE a.advisor_id = CAST(:advisor_id AS UUID)
            GROUP BY c.client_id, c.client_code, c.full_name, c.client_tier
            ORDER BY total_aum_usd DESC
            """
        ),
        {"advisor_id": adv_uuid},
    ).mappings().all()
    return [dict(r) for r in rows]


@router.get("/advisors/{advisor_id}/summary")
def api_get_advisor_summary(
    advisor_id: str,
    quarter_code: str = Query("2026-Q3"),
    db: Session = Depends(get_db),
):
    adv_uuid = _validate_uuid_or_422(advisor_id, "advisor_id")
    perf = db.execute(
        text(
            """
            SELECT advisor_id::TEXT, advisor_code, advisor_name, segment_name,
                   opening_assets_usd, closing_assets_usd, aum_growth_usd,
                   gross_inflows_usd, gross_outflows_usd, external_net_flows_usd,
                   firm_style_nna_usd, market_movement_usd, fees_and_commissions_usd,
                   internal_transfers_usd, unexplained_residual_usd, nna_rank, outflow_rank
            FROM marts.advisor_quarterly_performance
            WHERE advisor_id = CAST(:advisor_id AS UUID) AND quarter_code = :quarter_code
            """
        ),
        {"advisor_id": adv_uuid, "quarter_code": quarter_code},
    ).mappings().first()
    if not perf:
        raise HTTPException(status_code=404, detail="Advisor not found for quarter")

    acct_dist = db.execute(
        text(
            """
            SELECT a.account_type, COUNT(DISTINCT a.account_id) AS account_count,
                   COALESCE(SUM(av.total_aum_usd), 0)::NUMERIC(18, 2) AS total_aum_usd
            FROM raw.accounts a
            LEFT JOIN raw.account_valuations av
                ON av.account_id = a.account_id AND av.as_of_date = '2026-09-30'
            WHERE a.advisor_id = CAST(:advisor_id AS UUID)
            GROUP BY a.account_type
            ORDER BY total_aum_usd DESC
            """
        ),
        {"advisor_id": adv_uuid},
    ).mappings().all()

    top_households = db.execute(
        text(
            """
            SELECT c.client_id::TEXT, c.client_code, c.full_name, c.client_tier,
                   COALESCE(SUM(av.total_aum_usd), 0)::NUMERIC(18, 2) AS total_aum_usd,
                   COALESCE(SUM(ABS(t.net_amount)) FILTER (WHERE t.event_type IN ('EXTERNAL_WITHDRAWAL', 'EXTERNAL_TRANSFER_OUT')), 0)::NUMERIC(18, 2) AS q3_outflows_usd
            FROM raw.accounts a
            JOIN raw.clients c ON c.client_id = a.client_id
            LEFT JOIN raw.account_valuations av
                ON av.account_id = a.account_id AND av.as_of_date = '2026-09-30'
            LEFT JOIN raw.transaction_events t
                ON t.account_id = a.account_id AND t.effective_date BETWEEN '2026-07-01' AND '2026-09-30'
            WHERE a.advisor_id = CAST(:advisor_id AS UUID)
            GROUP BY c.client_id, c.client_code, c.full_name, c.client_tier
            ORDER BY q3_outflows_usd DESC, total_aum_usd DESC
            LIMIT 10
            """
        ),
        {"advisor_id": adv_uuid},
    ).mappings().all()

    return {
        "performance": dict(perf),
        "account_distribution": [dict(r) for r in acct_dist],
        "top_clients": [dict(r) for r in top_households],
    }


@router.get("/clients", response_model=PaginatedResponse[ClientItem])
def api_list_clients(
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    items, meta = list_clients(db, search, page, page_size)
    return PaginatedResponse(items=items, pagination=meta)


@router.get("/clients/{client_id}")
def api_get_client(client_id: str, db: Session = Depends(get_db)):
    cid = _validate_uuid_or_422(client_id, "client_id")
    client = db.execute(
        text(
            """
            SELECT client_id::TEXT, client_code, full_name, client_tier, risk_profile, onboarding_date, status
            FROM raw.clients
            WHERE client_id = CAST(:client_id AS UUID)
            """
        ),
        {"client_id": cid},
    ).mappings().first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    accounts = db.execute(
        text(
            """
            SELECT a.account_id::TEXT, a.account_number, a.account_type, a.status,
                   av.total_aum_usd AS latest_aum_usd
            FROM raw.accounts a
            LEFT JOIN raw.account_valuations av
                ON av.account_id = a.account_id AND av.as_of_date = '2026-09-30'
            WHERE a.client_id = CAST(:client_id AS UUID)
            """
        ),
        {"client_id": cid},
    ).mappings().all()
    return {**dict(client), "accounts": [dict(a) for a in accounts]}


@router.get("/accounts/{account_id}/details")
def api_get_account_details(account_id: str, db: Session = Depends(get_db)):
    aid = _validate_uuid_or_422(account_id, "account_id")
    acct = db.execute(
        text(
            """
            SELECT a.account_id::TEXT, a.account_number, a.account_type, a.opened_date, a.status,
                   c.client_id::TEXT, c.client_code, c.full_name AS client_name,
                   adv.advisor_id::TEXT, adv.advisor_code, adv.full_name AS advisor_name,
                   bs.segment_name
            FROM raw.accounts a
            JOIN raw.clients c ON c.client_id = a.client_id
            JOIN raw.advisors adv ON adv.advisor_id = a.advisor_id
            JOIN raw.business_segments bs ON bs.segment_id = a.segment_id
            WHERE a.account_id = CAST(:aid AS UUID)
            """
        ),
        {"aid": aid},
    ).mappings().first()
    if not acct:
        raise HTTPException(status_code=404, detail="Account not found")

    valuations = db.execute(
        text(
            """
            SELECT av.as_of_date, av.cash_value_usd, av.securities_value_usd, av.total_aum_usd
            FROM raw.account_valuations av
            JOIN raw.calendar cal ON cal.calendar_date = av.as_of_date
            WHERE av.account_id = CAST(:aid AS UUID) AND cal.is_month_end = TRUE
            ORDER BY av.as_of_date
            """
        ),
        {"aid": aid},
    ).mappings().all()

    positions = db.execute(
        text(
            """
            SELECT s.ticker, s.security_name, ac.asset_class_name,
                   ps.quantity, ps.market_price_usd, ps.market_value_usd
            FROM raw.position_snapshots ps
            JOIN raw.securities s ON s.security_id = ps.security_id
            JOIN raw.asset_classes ac ON ac.asset_class_id = s.asset_class_id
            WHERE ps.account_id = CAST(:aid AS UUID) AND ps.as_of_date = '2026-09-30'
            ORDER BY ps.market_value_usd DESC
            """
        ),
        {"aid": aid},
    ).mappings().all()

    assignments = db.execute(
        text(
            """
            SELECT aah.effective_from, aah.effective_to, aah.is_current, aah.assignment_reason,
                   adv.advisor_code, adv.full_name AS advisor_name
            FROM raw.advisor_assignment_history aah
            JOIN raw.advisors adv ON adv.advisor_id = aah.advisor_id
            WHERE aah.account_id = CAST(:aid AS UUID)
            ORDER BY aah.effective_from DESC
            """
        ),
        {"aid": aid},
    ).mappings().all()

    return {
        "account": dict(acct),
        "valuations": [dict(v) for v in valuations],
        "positions": [dict(p) for p in positions],
        "assignments": [dict(a) for a in assignments],
    }


@router.get("/accounts/{account_id}/transactions")
def api_get_account_transactions(
    account_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    aid = _validate_uuid_or_422(account_id, "account_id")
    offset = (page - 1) * page_size
    total = db.execute(
        text("SELECT COUNT(*) FROM staging.stg_transactions WHERE account_id = CAST(:aid AS UUID)"),
        {"aid": aid},
    ).scalar_one()
    rows = db.execute(
        text(
            """
            SELECT event_id::TEXT, external_ref, event_type, flow_classification,
                   effective_date, posted_date, gross_amount, fee_amount, net_amount,
                   nna_eligible, external_flow_eligible, is_internal_transfer
            FROM staging.stg_transactions
            WHERE account_id = CAST(:aid AS UUID)
            ORDER BY effective_date DESC, event_id
            LIMIT :limit OFFSET :offset
            """
        ),
        {"aid": aid, "limit": page_size, "offset": offset},
    ).mappings().all()
    return {
        "items": [dict(r) for r in rows],
        "pagination": PaginationMeta(
            page=page,
            page_size=page_size,
            total_items=int(total),
            total_pages=max(1, math.ceil(int(total) / page_size)),
        ),
    }


@router.get("/segments", response_model=list[SegmentItem])
def api_list_segments(quarter_code: str = Query("2026-Q3"), db: Session = Depends(get_db)):
    return list_segments(db, quarter_code)


@router.get("/flows")
def api_get_flows(
    start_date: date = Query(date(2024, 10, 1)),
    end_date: date = Query(DEFAULT_END),
    segment_id: str | None = Query(None),
    db: Session = Depends(get_db),
):
    if segment_id:
        seg_uuid = _validate_uuid_or_422(segment_id, "segment_id")
        rows = db.execute(
            text(
                """
                SELECT
                    b.period_code,
                    b.start_date,
                    b.end_date,
                    COALESCE(SUM(b.opening_assets_usd), 0)::NUMERIC(18, 2) AS opening_assets_usd,
                    COALESCE(SUM(b.actual_closing_assets_usd), 0)::NUMERIC(18, 2) AS closing_assets_usd,
                    COALESCE(SUM(b.gross_inflows_usd), 0)::NUMERIC(18, 2) AS gross_inflows_usd,
                    COALESCE(SUM(b.gross_outflows_usd), 0)::NUMERIC(18, 2) AS gross_outflows_usd,
                    COALESCE(SUM(b.external_net_flows_usd), 0)::NUMERIC(18, 2) AS external_net_flows_usd,
                    COALESCE(SUM(b.firm_style_nna_usd), 0)::NUMERIC(18, 2) AS firm_style_nna_usd,
                    COALESCE(SUM(b.price_driven_market_movement_usd), 0)::NUMERIC(18, 2) AS market_driven_movement_usd,
                    COALESCE(SUM(b.fees_and_commissions_usd), 0)::NUMERIC(18, 2) AS fees_and_commissions_usd
                FROM marts.mv_account_monthly_bridge b
                WHERE b.end_date BETWEEN :start_date AND :end_date
                  AND b.segment_id = CAST(:segment_id AS UUID)
                GROUP BY b.period_code, b.start_date, b.end_date
                ORDER BY b.end_date
                """
            ),
            {"start_date": start_date, "end_date": end_date, "segment_id": seg_uuid},
        ).mappings().all()
        return [dict(r) for r in rows]

    rows = db.execute(
        text(
            """
            SELECT period_code, start_date, end_date,
                   opening_assets_usd, closing_assets_usd,
                   gross_inflows_usd, gross_outflows_usd,
                   external_net_flows_usd, firm_style_nna_usd,
                   market_driven_movement_usd, fees_and_commissions_usd,
                   rolling_3m_nna_usd
            FROM marts.enterprise_monthly_kpis
            WHERE end_date BETWEEN :start_date AND :end_date
            ORDER BY end_date
            """
        ),
        {"start_date": start_date, "end_date": end_date},
    ).mappings().all()
    return [dict(r) for r in rows]


@router.get("/transactions")
def api_list_transactions(
    event_type: str | None = Query(None),
    start_date: date = Query(DEFAULT_START),
    end_date: date = Query(DEFAULT_END),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    clauses = ["effective_date BETWEEN :start_date AND :end_date"]
    params: dict = {"start_date": start_date, "end_date": end_date}
    if event_type:
        clauses.append("event_type = :event_type")
        params["event_type"] = event_type
    where_sql = " AND ".join(clauses)

    total = db.execute(
        text(f"SELECT COUNT(*) FROM staging.stg_transactions WHERE {where_sql}"), params
    ).scalar_one()
    params["limit"] = page_size
    params["offset"] = (page - 1) * page_size
    rows = db.execute(
        text(
            f"""
            SELECT event_id::TEXT, external_ref, account_id::TEXT, advisor_id::TEXT,
                   event_type, flow_classification, effective_date, posted_date,
                   gross_amount, fee_amount, net_amount, nna_eligible, is_late_posted
            FROM staging.stg_transactions
            WHERE {where_sql}
            ORDER BY effective_date DESC, event_id
            LIMIT :limit OFFSET :offset
            """
        ),
        params,
    ).mappings().all()
    return {
        "items": [dict(r) for r in rows],
        "pagination": PaginationMeta(
            page=page,
            page_size=page_size,
            total_items=int(total),
            total_pages=max(1, math.ceil(int(total) / page_size)),
        ),
    }


@router.get("/reconciliation", response_model=list[ReconciliationIssueOut])
def api_list_reconciliation(db: Session = Depends(get_db)):
    return discover_reconciliation_issues(db)


@router.get("/reconciliation/{issue_id}", response_model=ReconciliationIssueOut)
def api_get_reconciliation_issue(issue_id: str, db: Session = Depends(get_db)):
    issues = discover_reconciliation_issues(db)
    target = next((i for i in issues if i.issue_id == issue_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Reconciliation issue not found")
    return target


@router.post("/reconciliation/{issue_id}/acknowledge", response_model=ReconciliationIssueOut)
def api_acknowledge_reconciliation_issue(issue_id: str, db: Session = Depends(get_db)):
    res = acknowledge_issue_demo(db, issue_id)
    if not res:
        raise HTTPException(status_code=404, detail="Reconciliation issue not found")
    return res


@router.get("/investigations/templates")
def api_list_investigation_templates():
    return [
        {"template_id": t.template_id, "title": t.title, "description": t.description}
        for t in TEMPLATES.values()
    ]


@router.post("/investigations/run", response_model=InvestigationResponse)
def api_run_investigation(payload: InvestigationRequest, db: Session = Depends(get_db)):
    try:
        return run_investigation(
            db,
            template_id=payload.template_id,
            quarter_code=payload.quarter_code,
            advisor_code=payload.advisor_code,
            limit=payload.limit,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/investigations/parse-intent")
def api_parse_investigation_intent(payload: dict):
    query_text = str(payload.get("query", ""))
    return parse_constrained_intent(query_text)


@router.get("/investigations/saved")
def api_list_saved_investigations(db: Session = Depends(get_db)):
    return list_saved_investigations(db)


@router.post("/investigations/saved")
def api_save_investigation(payload: dict, db: Session = Depends(get_db)):
    return save_investigation_record(db, payload)


@router.get("/period-compare")
def api_period_compare(
    current_quarter: str = Query("2026-Q3"),
    prior_quarter: str = Query("2026-Q2"),
    db: Session = Depends(get_db),
):
    from decimal import ROUND_HALF_UP, Decimal

    def _q_bounds(qcode: str):
        row = db.execute(
            text("SELECT start_date, end_date FROM raw.reporting_periods WHERE period_code = :c AND period_type = 'QUARTERLY'"),
            {"c": qcode},
        ).mappings().first()
        if not row:
            raise HTTPException(status_code=404, detail=f"Unknown quarter_code: {qcode}")
        return row["start_date"], row["end_date"]

    cur_s, cur_e = _q_bounds(current_quarter)
    pri_s, pri_e = _q_bounds(prior_quarter)
    cur_ov = get_overview(db, cur_s, cur_e)
    pri_ov = get_overview(db, pri_s, pri_e)

    def _cmp(label: str, cur_val: Decimal, pri_val: Decimal):
        diff = (cur_val - pri_val).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        pct = (
            ((diff / abs(pri_val)) * Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            if pri_val != Decimal("0.00")
            else None
        )
        return {
            "metric": label,
            "current_usd": f"{cur_val:.2f}",
            "prior_usd": f"{pri_val:.2f}",
            "abs_change_usd": f"{diff:.2f}",
            "pct_change": f"{pct:.2f}" if pct is not None else None,
        }

    metrics = [
        _cmp("Closing Assets", cur_ov.closing_assets_usd, pri_ov.closing_assets_usd),
        _cmp("Firm-Style NNA", cur_ov.firm_style_nna_usd, pri_ov.firm_style_nna_usd),
        _cmp("External Net Flows", cur_ov.external_net_flows_usd, pri_ov.external_net_flows_usd),
        _cmp("Market Movement", cur_ov.market_driven_movement_usd, pri_ov.market_driven_movement_usd),
        _cmp("Fee-Based Assets", cur_ov.fee_based_assets_usd, pri_ov.fee_based_assets_usd),
    ]

    rank_shifts = db.execute(
        text(
            """
            SELECT c.advisor_code, c.advisor_name,
                   p.nna_rank AS prior_rank, c.nna_rank AS current_rank,
                   (p.nna_rank - c.nna_rank) AS rank_improvement,
                   c.firm_style_nna_usd AS current_nna_usd,
                   p.firm_style_nna_usd AS prior_nna_usd
            FROM marts.advisor_quarterly_performance c
            JOIN marts.advisor_quarterly_performance p
              ON p.advisor_id = c.advisor_id AND p.quarter_code = :prior_q
            WHERE c.quarter_code = :cur_q
            ORDER BY ABS(p.nna_rank - c.nna_rank) DESC
            LIMIT 10
            """
        ),
        {"cur_q": current_quarter, "prior_q": prior_quarter},
    ).mappings().all()

    return {
        "current_quarter": current_quarter,
        "prior_quarter": prior_quarter,
        "methodology": "Absolute dollar change = Current - Prior; Percentage change = (Current - Prior) / |Prior| * 100 (NULL if Prior is 0).",
        "metrics": metrics,
        "ranking_changes": [dict(r) for r in rank_shifts],
    }


@router.get("/exports/excel")
def api_export_excel(
    start_date: date = Query(DEFAULT_START),
    end_date: date = Query(DEFAULT_END),
    quarter_code: str = Query("2026-Q3"),
    segment_id: str | None = Query(None),
    db: Session = Depends(get_db),
):
    content = generate_quarterly_excel(db, start_date, end_date, quarter_code, segment_id)
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": 'attachment; filename="AUMVerity_Wealth_Management_Quarterly_Report.xlsx"'
        },
    )


@router.get("/exports/tableau/{dataset_name}.csv")
def api_export_tableau_csv(
    dataset_name: str,
    start_date: date = Query(DEFAULT_START),
    end_date: date = Query(DEFAULT_END),
    quarter_code: str = Query("2026-Q3"),
    db: Session = Depends(get_db),
):
    try:
        csv_text = generate_tableau_csv(db, dataset_name, start_date, end_date, quarter_code)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(
        content=csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{dataset_name}.csv"'},
    )
