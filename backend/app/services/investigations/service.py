from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
import json
import uuid

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.schemas.analytics import InvestigationResponse


@dataclass(frozen=True)
class InvestigationTemplate:
    template_id: str
    title: str
    description: str
    sql: str


TEMPLATES: dict[str, InvestigationTemplate] = {
    "top5_outflow_advisors": InvestigationTemplate(
        template_id="top5_outflow_advisors",
        title="Top five advisors by largest external net outflows",
        description="Identifies advisors with the largest negative external net flows in the selected quarter.",
        sql="""
            SELECT advisor_id::TEXT, advisor_code, advisor_name, segment_name,
                   opening_assets_usd, closing_assets_usd,
                   gross_inflows_usd, gross_outflows_usd, external_net_flows_usd,
                   firm_style_nna_usd, market_movement_usd
            FROM marts.advisor_quarterly_performance
            WHERE quarter_code = :quarter_code
            ORDER BY external_net_flows_usd ASC
            LIMIT :limit
        """,
    ),
    "pos_aum_neg_nna_advisors": InvestigationTemplate(
        template_id="pos_aum_neg_nna_advisors",
        title="Advisors with positive AUM growth but negative NNA",
        description="Advisors whose assets grew due to market appreciation despite negative Net New Assets.",
        sql="""
            SELECT advisor_id::TEXT, advisor_code, advisor_name, segment_name,
                   aum_growth_usd, firm_style_nna_usd, market_movement_usd, external_net_flows_usd
            FROM marts.advisor_quarterly_performance
            WHERE quarter_code = :quarter_code
              AND aum_growth_usd > 0
              AND firm_style_nna_usd < 0
            ORDER BY aum_growth_usd DESC
            LIMIT :limit
        """,
    ),
    "segment_nna_vs_market": InvestigationTemplate(
        template_id="segment_nna_vs_market",
        title="Highest-growing wealth-management segments",
        description="Compares organic Firm-Style NNA against price-driven market appreciation by business segment.",
        sql="""
            SELECT segment_id::TEXT, segment_code, segment_name, opening_assets_usd, closing_assets_usd,
                   total_growth_usd, firm_style_nna_usd, market_movement_usd, nna_growth_rate_pct
            FROM marts.segment_quarterly_contribution
            WHERE quarter_code = :quarter_code
            ORDER BY total_growth_usd DESC
            LIMIT :limit
        """,
    ),
    "largest_client_withdrawals": InvestigationTemplate(
        template_id="largest_client_withdrawals",
        title="Largest concentrated client withdrawals",
        description="Ranks client households driving the largest gross external outflows in the selected quarter.",
        sql="""
            WITH cl_out AS (
                SELECT c.client_id::TEXT, c.client_code, c.full_name AS client_name,
                       a.advisor_code,
                       SUM(ABS(t.net_amount))::NUMERIC(18,2) AS gross_outflows_usd,
                       COUNT(*) AS withdrawal_count
                FROM raw.transaction_events t
                JOIN raw.reporting_periods rp ON rp.period_code = :quarter_code AND rp.period_type = 'QUARTERLY'
                JOIN raw.accounts acct ON acct.account_id = t.account_id
                JOIN raw.clients c ON c.client_id = acct.client_id
                JOIN raw.advisors a ON a.advisor_id = t.advisor_id
                WHERE t.effective_date BETWEEN rp.start_date AND rp.end_date
                  AND t.event_type IN ('EXTERNAL_WITHDRAWAL', 'EXTERNAL_TRANSFER_OUT')
                GROUP BY c.client_id, c.client_code, c.full_name, a.advisor_code
            )
            SELECT client_id, client_code, client_name, advisor_code, gross_outflows_usd, withdrawal_count,
                   ROUND((gross_outflows_usd / NULLIF(SUM(gross_outflows_usd) OVER (), 0)) * 100, 2) AS share_of_total_outflows_pct
            FROM cl_out
            ORDER BY gross_outflows_usd DESC
            LIMIT :limit
        """,
    ),
    "largest_market_increases": InvestigationTemplate(
        template_id="largest_market_increases",
        title="Largest market-driven asset increases",
        description="Advisors and segments with the largest positive price-driven market appreciation.",
        sql="""
            SELECT advisor_id::TEXT, advisor_code, advisor_name, segment_name,
                   opening_assets_usd, closing_assets_usd, market_movement_usd, firm_style_nna_usd
            FROM marts.advisor_quarterly_performance
            WHERE quarter_code = :quarter_code
            ORDER BY market_movement_usd DESC
            LIMIT :limit
        """,
    ),
    "fee_based_asset_movement": InvestigationTemplate(
        template_id="fee_based_asset_movement",
        title="Fee-based asset movement",
        description="Monthly progression of Fee-based advisory assets and NNA flows.",
        sql="""
            SELECT period_code, start_date::TEXT, end_date::TEXT,
                   fee_based_assets_usd, fee_based_asset_flows_usd,
                   estimated_annual_fee_revenue_proxy_usd
            FROM marts.enterprise_monthly_kpis
            ORDER BY end_date DESC
            LIMIT :limit
        """,
    ),
    "material_reconciliation_discrepancies": InvestigationTemplate(
        template_id="material_reconciliation_discrepancies",
        title="Material reconciliation discrepancies",
        description="Reported accounts in 2026-09-30 that do not reconcile against reconstructed ledger totals.",
        sql="""
            SELECT account_id::TEXT, account_number, as_of_date::TEXT,
                   feed_row_count, expected_aum_usd, reported_aum_usd, aum_diff_usd,
                   expected_nna_usd, reported_nna_usd, nna_diff_usd,
                   advisor_mismatch, segment_mismatch
            FROM marts.q_i_unreconciled_reported_accounts
            ORDER BY ABS(aum_diff_usd) DESC
            LIMIT :limit
        """,
    ),
    "advisor_client_outflows": InvestigationTemplate(
        template_id="advisor_client_outflows",
        title="Advisor Client Outflow Concentration",
        description="Ranks client households driving external outflows for a specific advisor.",
        sql="""
            WITH adv_out AS (
                SELECT c.client_id::TEXT, c.client_code, c.full_name AS client_name,
                       SUM(ABS(t.net_amount))::NUMERIC(18,2) AS client_outflows_usd
                FROM raw.transaction_events t
                JOIN raw.advisors a ON a.advisor_id = t.advisor_id
                JOIN raw.accounts acct ON acct.account_id = t.account_id
                JOIN raw.clients c ON c.client_id = acct.client_id
                WHERE a.advisor_code = :advisor_code
                  AND t.effective_date BETWEEN '2026-07-01' AND '2026-09-30'
                  AND t.event_type IN ('EXTERNAL_WITHDRAWAL', 'EXTERNAL_TRANSFER_OUT')
                GROUP BY c.client_id, c.client_code, c.full_name
            )
            SELECT client_id, client_code, client_name, client_outflows_usd,
                   ROUND((client_outflows_usd / NULLIF(SUM(client_outflows_usd) OVER (), 0)) * 100, 2) AS share_pct
            FROM adv_out
            ORDER BY client_outflows_usd DESC
            LIMIT :limit
        """,
    ),
}


def parse_constrained_intent(query_text: str) -> dict:
    """Constrained deterministic intent parser. Never executes or generates arbitrary SQL."""
    q = query_text.lower().strip()
    quarter = "2026-Q2" if "q2" in q else "2026-Q3"

    rules = [
        (["outflow", "advisor"], "top5_outflow_advisors"),
        (["positive aum", "negative nna"], "pos_aum_neg_nna_advisors"),
        (["segment", "grow"], "segment_nna_vs_market"),
        (["client", "withdrawal"], "largest_client_withdrawals"),
        (["concentrated", "withdrawal"], "largest_client_withdrawals"),
        (["market", "increase"], "largest_market_increases"),
        (["fee-based", "fee based"], "fee_based_asset_movement"),
        (["reconcil", "discrepanc"], "material_reconciliation_discrepancies"),
    ]
    for keywords, tid in rules:
        if any(kw in q for kw in keywords) and (len(keywords) == 1 or all(kw in q for kw in keywords)):
            return {
                "supported": True,
                "template_id": tid,
                "quarter_code": quarter,
                "message": f"Mapped request to validated investigation: '{TEMPLATES[tid].title}'.",
            }
    return {
        "supported": False,
        "template_id": None,
        "quarter_code": quarter,
        "message": (
            "Unsupported query intent. Please select one of the validated analytical investigations "
            "(e.g., top outflow advisors, positive AUM / negative NNA, segment growth, client withdrawals, "
            "market increases, fee-based movement, or reconciliation discrepancies)."
        ),
    }


def run_investigation(
    db: Session,
    template_id: str,
    quarter_code: str = "2026-Q3",
    advisor_code: str | None = None,
    limit: int = 20,
) -> InvestigationResponse:
    if template_id not in TEMPLATES:
        raise KeyError(f"Unknown investigation template: {template_id}")

    tpl = TEMPLATES[template_id]
    safe_limit = max(1, min(limit, 100))
    params: dict = {
        "quarter_code": quarter_code,
        "advisor_code": advisor_code or "ADV-001",
        "limit": safe_limit,
    }
    raw_rows = db.execute(text(tpl.sql), params).mappings().all()
    rows = [
        {k: (f"{v:.2f}" if isinstance(v, Decimal) else v) for k, v in dict(r).items()}
        for r in raw_rows
    ]
    narrative = (
        f"Observed evidence: Executed '{tpl.title}' for {quarter_code}, returning {len(rows)} record(s) "
        f"from verified PostgreSQL marts."
    )
    return InvestigationResponse(
        template_id=tpl.template_id,
        title=tpl.title,
        description=tpl.description,
        sql_template=tpl.sql.strip(),
        query_version=get_settings().CALCULATION_VERSION,
        rows=rows,
        narrative=narrative,
    )


def save_investigation_record(db: Session, payload: dict) -> dict:
    inv_id = str(uuid.uuid4())
    created_at = datetime.now(UTC).isoformat()
    record = {
        "investigation_id": inv_id,
        "name": payload.get("name", "Untitled Investigation"),
        "template_id": payload.get("template_id"),
        "quarter_code": payload.get("quarter_code", "2026-Q3"),
        "filters": payload.get("filters", {}),
        "selected_metric": payload.get("selected_metric"),
        "calculation_version": get_settings().CALCULATION_VERSION,
        "created_at": created_at,
    }
    db.execute(
        text(
            """
            INSERT INTO raw.audit_events (audit_id, actor, action, entity_type, entity_id, payload_json)
            VALUES (:audit_id, 'analyst_demo', 'SAVED_INVESTIGATION', 'saved_investigation', :entity_id, CAST(:payload AS JSONB))
            """
        ),
        {
            "audit_id": str(uuid.uuid4()),
            "entity_id": inv_id,
            "payload": json.dumps(record),
        },
    )
    db.commit()
    return record


def list_saved_investigations(db: Session) -> list[dict]:
    rows = db.execute(
        text(
            """
            SELECT payload_json
            FROM raw.audit_events
            WHERE entity_type = 'saved_investigation' AND action = 'SAVED_INVESTIGATION'
            ORDER BY created_at DESC
            LIMIT 25
            """
        )
    ).mappings().all()
    return [r["payload_json"] for r in rows]
