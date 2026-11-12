from datetime import UTC, date, datetime
from decimal import Decimal
import io

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.lineage import METRIC_REGISTRY
from app.services.metrics.service import (
    get_asset_bridge,
    get_overview,
    list_advisors,
    list_segments,
)
from app.services.reconciliation.service import discover_reconciliation_issues

HEADER_FILL = PatternFill(start_color="122D33", end_color="122D33", fill_type="solid")
HEADER_FONT = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
FORMULA_FILL = PatternFill(start_color="EBF3F1", end_color="EBF3F1", fill_type="solid")
FORMULA_FONT = Font(name="Calibri", size=10, bold=True, color="122D33")
TITLE_FONT = Font(name="Calibri", size=13, bold=True, color="122D33")
CURR_FMT = '$#,##0.00;($#,##0.00);"-"'
PCT_FMT = "0.00%"


def _style_table_sheet(ws, headers: list[str], start_row: int = 1) -> None:
    for idx, h in enumerate(headers, start=1):
        cell = ws.cell(row=start_row, column=idx, value=h)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="left", vertical="center")
    ws.freeze_panes = f"A{start_row + 1}"
    ws.auto_filter.ref = f"A{start_row}:{get_column_letter(len(headers))}{start_row}"


def _auto_fit(ws) -> None:
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            val = str(cell.value or "")
            if not val.startswith("="):
                max_len = max(max_len, len(val))
        ws.column_dimensions[col_letter].width = min(max(max_len + 4, 14), 44)


def generate_quarterly_excel(
    db: Session,
    start_date: date,
    end_date: date,
    quarter_code: str = "2026-Q3",
    segment_id: str | None = None,
) -> bytes:
    settings = get_settings()
    wb = Workbook()

    ov = get_overview(db, start_date, end_date, segment_id=segment_id)
    bridge = get_asset_bridge(db, start_date, end_date, segment_id=segment_id)
    advisors, _ = list_advisors(db, quarter_code=quarter_code, segment_id=segment_id, page_size=100)
    segments = list_segments(db, quarter_code=quarter_code)
    issues = discover_reconciliation_issues(db)

    # 01 Executive Summary
    ws1 = wb.active
    ws1.title = "01 Executive Summary"
    ws1["A1"] = "AUMVERITY — Wealth Intelligence & Asset Movement Report (SYNTHETIC DATA)"
    ws1["A1"].font = TITLE_FONT
    ws1["A2"] = f"Period: {start_date.isoformat()} to {end_date.isoformat()} | Currency: USD | Model: {settings.CALCULATION_VERSION}"
    _style_table_sheet(ws1, ["Metric", "Value (USD / %)", "Source / Notes"], start_row=4)
    summary_rows = [
        ("Opening Assets", float(ov.opening_assets_usd), "marts.mv_account_monthly_bridge"),
        ("Closing Assets", float(ov.closing_assets_usd), "marts.mv_account_monthly_bridge"),
        ("Total Asset Growth", "=B6-B5", "Excel formula: Closing - Opening"),
        ("Firm-Style Net New Assets (NNA)", float(ov.firm_style_nna_usd), "Includes credited income"),
        ("External Net Flows", float(ov.external_net_flows_usd), "External deposits/transfers - outflows"),
        ("Gross Inflows", float(ov.gross_inflows_usd), "External inflows & in-kind"),
        ("Gross Outflows", float(-ov.gross_outflows_usd), "External withdrawals & transfers out"),
        ("Price-Driven Market Movement", float(ov.market_driven_movement_usd), "Position-level attribution"),
        ("Fees & Commissions", float(-ov.fees_and_commissions_usd), "Explicit fee deduction"),
        ("Fee-Based Assets", float(ov.fee_based_assets_usd), "Fee-based advisory perimeter"),
        ("Unexplained Residual", float(ov.unexplained_residual_usd), "Never concealed in market movement"),
    ]
    for idx, (label, val, note) in enumerate(summary_rows, start=5):
        ws1.cell(row=idx, column=1, value=label)
        c = ws1.cell(row=idx, column=2, value=val)
        c.number_format = CURR_FMT
        if isinstance(val, str) and val.startswith("="):
            c.fill = FORMULA_FILL
            c.font = FORMULA_FONT
        ws1.cell(row=idx, column=3, value=note)
    _auto_fit(ws1)

    # 02 Asset Movement Bridge (with live Excel reconciliation formulas)
    ws2 = wb.create_sheet("02 Asset Movement Bridge")
    _style_table_sheet(ws2, ["Step", "Component", "Amount (USD)", "Classification"])
    for idx, step in enumerate(bridge.steps, start=2):
        ws2.cell(row=idx, column=1, value=step.step_key)
        ws2.cell(row=idx, column=2, value=step.label)
        c = ws2.cell(row=idx, column=3, value=float(step.amount_usd))
        c.number_format = CURR_FMT
        ws2.cell(row=idx, column=4, value=step.step_type)

    # Verification row using live SUM formula
    last_step_row = 1 + len(bridge.steps)
    calc_row = last_step_row + 2
    ws2.cell(row=calc_row, column=2, value="Formula Check: Reconstructed Closing (Opening + Movements)")
    c_rec = ws2.cell(row=calc_row, column=3, value=f"=SUM(C2:C{last_step_row - 1})")
    c_rec.number_format = CURR_FMT
    c_rec.fill = FORMULA_FILL
    c_rec.font = FORMULA_FONT

    diff_row = calc_row + 1
    ws2.cell(row=diff_row, column=2, value="Formula Check: Difference (Actual Closing - Reconstructed)")
    c_diff = ws2.cell(row=diff_row, column=3, value=f"=C{last_step_row}-C{calc_row}")
    c_diff.number_format = CURR_FMT
    c_diff.fill = FORMULA_FILL
    c_diff.font = FORMULA_FONT
    _auto_fit(ws2)

    # 03 Advisor Performance
    ws3 = wb.create_sheet("03 Advisor Performance")
    _style_table_sheet(
        ws3,
        [
            "Advisor Code", "Advisor Name", "Segment", "Opening Assets", "Closing Assets",
            "Gross Inflows", "Gross Outflows", "External Net Flows", "Firm-Style NNA",
            "Market Movement", "Period Growth", "NNA Rank",
        ],
    )
    for idx, a in enumerate(advisors, start=2):
        ws3.cell(row=idx, column=1, value=a.advisor_code)
        ws3.cell(row=idx, column=2, value=a.advisor_name)
        ws3.cell(row=idx, column=3, value=a.segment_name)
        vals = [
            float(a.opening_assets_usd), float(a.closing_assets_usd), float(a.gross_inflows_usd),
            float(-a.gross_outflows_usd), float(a.external_net_flows_usd), float(a.firm_style_nna_usd),
            float(a.market_movement_usd), f"=E{idx}-D{idx}",
        ]
        for c_idx, v in enumerate(vals, start=4):
            cell = ws3.cell(row=idx, column=c_idx, value=v)
            cell.number_format = CURR_FMT
            if isinstance(v, str) and v.startswith("="):
                cell.fill = FORMULA_FILL
                cell.font = FORMULA_FONT
        ws3.cell(row=idx, column=12, value=a.nna_rank)
    _auto_fit(ws3)

    # 04 Business Segments
    ws4 = wb.create_sheet("04 Business Segments")
    _style_table_sheet(
        ws4,
        ["Segment Code", "Segment Name", "Opening Assets", "Closing Assets", "Total Growth", "Firm-Style NNA", "Market Movement", "AUM Share %"],
    )
    for idx, s in enumerate(segments, start=2):
        ws4.cell(row=idx, column=1, value=s.segment_code)
        ws4.cell(row=idx, column=2, value=s.segment_name)
        for c_idx, v in enumerate(
            [float(s.opening_assets_usd), float(s.closing_assets_usd), f"=D{idx}-C{idx}", float(s.firm_style_nna_usd), float(s.market_movement_usd)],
            start=3,
        ):
            cell = ws4.cell(row=idx, column=c_idx, value=v)
            cell.number_format = CURR_FMT
            if isinstance(v, str) and v.startswith("="):
                cell.fill = FORMULA_FILL
                cell.font = FORMULA_FONT
        sh = ws4.cell(row=idx, column=8, value=float(s.segment_aum_share_pct or 0) / 100.0)
        sh.number_format = PCT_FMT
    _auto_fit(ws4)

    # 05 Client Flow Analysis
    ws5 = wb.create_sheet("05 Client Flow Analysis")
    _style_table_sheet(ws5, ["Period", "Gross Inflows", "Gross Outflows", "External Net Flows", "Firm-Style NNA", "Market Movement", "Fees & Commissions"])
    flow_rows = db.execute(
        text(
            """
            SELECT period_code, gross_inflows_usd, gross_outflows_usd,
                   external_net_flows_usd, firm_style_nna_usd,
                   market_driven_movement_usd, fees_and_commissions_usd
            FROM marts.enterprise_monthly_kpis
            WHERE end_date BETWEEN :start_date AND :end_date
            ORDER BY end_date
            """
        ),
        {"start_date": start_date, "end_date": end_date},
    ).mappings().all()
    for idx, fr in enumerate(flow_rows, start=2):
        ws5.cell(row=idx, column=1, value=fr["period_code"])
        for c_idx, key in enumerate(
            ["gross_inflows_usd", "gross_outflows_usd", "external_net_flows_usd", "firm_style_nna_usd", "market_driven_movement_usd", "fees_and_commissions_usd"],
            start=2,
        ):
            val = float(fr[key])
            if key in ("gross_outflows_usd", "fees_and_commissions_usd"):
                val = -abs(val)
            cell = ws5.cell(row=idx, column=c_idx, value=val)
            cell.number_format = CURR_FMT
    _auto_fit(ws5)

    # 06 Reconciliation Exceptions
    ws6 = wb.create_sheet("06 Reconciliation Exceptions")
    _style_table_sheet(ws6, ["Issue Code", "Type", "Severity", "Period", "Scope", "Expected (USD)", "Reported (USD)", "Variance (USD)", "Status", "Reason"])
    for idx, iss in enumerate(issues, start=2):
        ws6.cell(row=idx, column=1, value=iss.issue_code)
        ws6.cell(row=idx, column=2, value=iss.issue_type)
        ws6.cell(row=idx, column=3, value=iss.severity)
        ws6.cell(row=idx, column=4, value=iss.affected_period)
        ws6.cell(row=idx, column=5, value=iss.affected_scope)
        for c_idx, v in enumerate([float(iss.expected_amount_usd), float(iss.reported_amount_usd), f"=G{idx}-F{idx}"], start=6):
            cell = ws6.cell(row=idx, column=c_idx, value=v)
            cell.number_format = CURR_FMT
            if isinstance(v, str) and v.startswith("="):
                cell.fill = FORMULA_FILL
                cell.font = FORMULA_FONT
        ws6.cell(row=idx, column=9, value=iss.status)
        ws6.cell(row=idx, column=10, value=iss.likely_reason)
    _auto_fit(ws6)

    # 07 Source Data (Top 100 Q3 transactions sample)
    ws7 = wb.create_sheet("07 Source Data")
    _style_table_sheet(ws7, ["External Ref", "Event Type", "Classification", "Effective Date", "Posted Date", "Gross Amount", "Fee Amount", "Net Amount"])
    tx_rows = db.execute(
        text(
            """
            SELECT external_ref, event_type, flow_classification, effective_date, posted_date,
                   gross_amount, fee_amount, net_amount
            FROM staging.stg_transactions
            WHERE effective_date BETWEEN :start_date AND :end_date
            ORDER BY ABS(net_amount) DESC
            LIMIT 100
            """
        ),
        {"start_date": start_date, "end_date": end_date},
    ).mappings().all()
    for idx, tx in enumerate(tx_rows, start=2):
        ws7.cell(row=idx, column=1, value=tx["external_ref"])
        ws7.cell(row=idx, column=2, value=tx["event_type"])
        ws7.cell(row=idx, column=3, value=tx["flow_classification"])
        ws7.cell(row=idx, column=4, value=tx["effective_date"].isoformat())
        ws7.cell(row=idx, column=5, value=tx["posted_date"].isoformat())
        for c_idx, key in enumerate(["gross_amount", "fee_amount", "net_amount"], start=6):
            cell = ws7.cell(row=idx, column=c_idx, value=float(tx[key]))
            cell.number_format = CURR_FMT
    _auto_fit(ws7)

    # 08 Metric Definitions
    ws8 = wb.create_sheet("08 Metric Definitions")
    _style_table_sheet(ws8, ["Metric ID", "Metric Name", "Category", "Formula", "SQL Model", "Inclusion Policy", "Exclusion Policy"])
    for idx, spec in enumerate(METRIC_REGISTRY.values(), start=2):
        ws8.cell(row=idx, column=1, value=spec.metric_id)
        ws8.cell(row=idx, column=2, value=spec.metric_name)
        ws8.cell(row=idx, column=3, value=spec.category)
        ws8.cell(row=idx, column=4, value=spec.formula)
        ws8.cell(row=idx, column=5, value=spec.sql_model)
        ws8.cell(row=idx, column=6, value=spec.inclusion_policy)
        ws8.cell(row=idx, column=7, value=spec.exclusion_policy)
    _auto_fit(ws8)

    # 09 Report Metadata
    ws9 = wb.create_sheet("09 Report Metadata")
    _style_table_sheet(ws9, ["Property", "Value"])
    meta_rows = [
        ("Application", "AUMVERITY — Wealth Intelligence & Asset Movement Analytics"),
        ("Data Classification", "SYNTHETIC DATA ONLY (Demonstration Portfolio)"),
        ("Reporting Period", f"{start_date.isoformat()} to {end_date.isoformat()} ({quarter_code})"),
        ("Segment Filter", segment_id or "ALL"),
        ("Reporting Currency", "USD"),
        ("Calculation Version", settings.CALCULATION_VERSION),
        ("Generated At (UTC)", datetime.now(UTC).isoformat()),
        ("Formula Policy", "Shaded cells contain live Excel formulas recalculated by Excel on open."),
    ]
    for idx, (k, v) in enumerate(meta_rows, start=2):
        ws9.cell(row=idx, column=1, value=k)
        ws9.cell(row=idx, column=2, value=v)
    _auto_fit(ws9)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
