import csv
from datetime import date
import io

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.metrics.service import get_asset_bridge, list_advisors, list_segments
from app.services.reconciliation.service import discover_reconciliation_issues

TABLEAU_DATASETS = {
    "advisor_performance",
    "asset_movement",
    "segment_performance",
    "monthly_flows",
    "reconciliation_exceptions",
}


def generate_tableau_csv(
    db: Session,
    dataset_name: str,
    start_date: date,
    end_date: date,
    quarter_code: str = "2026-Q3",
) -> str:
    if dataset_name not in TABLEAU_DATASETS:
        raise KeyError(f"Unknown Tableau dataset: {dataset_name}")

    buf = io.StringIO()
    writer = csv.writer(buf)

    if dataset_name == "advisor_performance":
        advisors, _ = list_advisors(db, quarter_code=quarter_code, page_size=100)
        writer.writerow([
            "quarter_code", "advisor_id", "advisor_code", "advisor_name", "segment_name",
            "opening_assets_usd", "closing_assets_usd", "aum_growth_usd",
            "gross_inflows_usd", "gross_outflows_usd", "external_net_flows_usd",
            "firm_style_nna_usd", "market_movement_usd", "nna_rank", "outflow_rank",
        ])
        for a in advisors:
            writer.writerow([
                quarter_code, a.advisor_id, a.advisor_code, a.advisor_name, a.segment_name,
                f"{a.opening_assets_usd:.2f}", f"{a.closing_assets_usd:.2f}", f"{a.aum_growth_usd:.2f}",
                f"{a.gross_inflows_usd:.2f}", f"{a.gross_outflows_usd:.2f}", f"{a.external_net_flows_usd:.2f}",
                f"{a.firm_style_nna_usd:.2f}", f"{a.market_movement_usd:.2f}", a.nna_rank, a.outflow_rank,
            ])

    elif dataset_name == "asset_movement":
        bridge = get_asset_bridge(db, start_date, end_date)
        writer.writerow(["start_date", "end_date", "step_key", "label", "amount_usd", "step_type"])
        for s in bridge.steps:
            writer.writerow([start_date.isoformat(), end_date.isoformat(), s.step_key, s.label, f"{s.amount_usd:.2f}", s.step_type])

    elif dataset_name == "segment_performance":
        segs = list_segments(db, quarter_code=quarter_code)
        writer.writerow([
            "quarter_code", "segment_id", "segment_code", "segment_name",
            "opening_assets_usd", "closing_assets_usd", "total_growth_usd",
            "firm_style_nna_usd", "external_net_flows_usd", "market_movement_usd",
            "nna_growth_rate_pct", "segment_aum_share_pct",
        ])
        for s in segs:
            writer.writerow([
                quarter_code, s.segment_id, s.segment_code, s.segment_name,
                f"{s.opening_assets_usd:.2f}", f"{s.closing_assets_usd:.2f}", f"{s.total_growth_usd:.2f}",
                f"{s.firm_style_nna_usd:.2f}", f"{s.external_net_flows_usd:.2f}", f"{s.market_movement_usd:.2f}",
                str(s.nna_growth_rate_pct or ""), str(s.segment_aum_share_pct or ""),
            ])

    elif dataset_name == "monthly_flows":
        rows = db.execute(
            text(
                """
                SELECT period_code, start_date, end_date, opening_assets_usd, closing_assets_usd,
                       gross_inflows_usd, gross_outflows_usd, external_net_flows_usd,
                       firm_style_nna_usd, market_driven_movement_usd, fees_and_commissions_usd
                FROM marts.enterprise_monthly_kpis
                ORDER BY end_date
                """
            )
        ).mappings().all()
        writer.writerow([
            "period_code", "start_date", "end_date", "opening_assets_usd", "closing_assets_usd",
            "gross_inflows_usd", "gross_outflows_usd", "external_net_flows_usd",
            "firm_style_nna_usd", "market_driven_movement_usd", "fees_and_commissions_usd",
        ])
        for r in rows:
            writer.writerow([
                r["period_code"], r["start_date"].isoformat(), r["end_date"].isoformat(),
                f"{r['opening_assets_usd']:.2f}", f"{r['closing_assets_usd']:.2f}",
                f"{r['gross_inflows_usd']:.2f}", f"{r['gross_outflows_usd']:.2f}",
                f"{r['external_net_flows_usd']:.2f}", f"{r['firm_style_nna_usd']:.2f}",
                f"{r['market_driven_movement_usd']:.2f}", f"{r['fees_and_commissions_usd']:.2f}",
            ])

    elif dataset_name == "reconciliation_exceptions":
        issues = discover_reconciliation_issues(db)
        writer.writerow([
            "issue_id", "issue_code", "issue_type", "severity", "affected_period",
            "affected_scope", "expected_amount_usd", "reported_amount_usd", "difference_usd", "status", "likely_reason",
        ])
        for i in issues:
            writer.writerow([
                i.issue_id, i.issue_code, i.issue_type, i.severity, i.affected_period,
                i.affected_scope, f"{i.expected_amount_usd:.2f}", f"{i.reported_amount_usd:.2f}",
                f"{i.difference_usd:.2f}", i.status, i.likely_reason,
            ])

    return buf.getvalue()
