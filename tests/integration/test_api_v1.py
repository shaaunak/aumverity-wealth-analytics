from decimal import Decimal

from fastapi.testclient import TestClient
import psycopg

from app.core.config import get_settings
from app.main import app

client = TestClient(app)


def test_v1_health_and_ready():
    assert client.get("/api/v1/health").status_code == 200
    r = client.get("/api/v1/ready")
    assert r.status_code == 200
    assert r.json()["database"] == "connected"


def test_v1_overview_and_bridge_tieout():
    ov_res = client.get("/api/v1/overview?start_date=2026-07-01&end_date=2026-09-30")
    assert ov_res.status_code == 200
    ov = ov_res.json()
    assert ov["data_classification"] == "SYNTHETIC"
    assert ov["currency"] == "USD"
    assert Decimal(ov["closing_assets_usd"]) > Decimal("0.00")

    br_res = client.get("/api/v1/asset-bridge?start_date=2026-07-01&end_date=2026-09-30")
    assert br_res.status_code == 200
    br = br_res.json()
    assert len(br["steps"]) == 9
    assert br["steps"][0]["amount_usd"] == ov["opening_assets_usd"]
    assert br["steps"][-1]["amount_usd"] == ov["closing_assets_usd"]


def test_v1_explainable_kpi_and_lineage():
    res = client.get("/api/v1/metrics/firm_style_nna?start_date=2026-07-01&end_date=2026-09-30")
    assert res.status_code == 200
    data = res.json()
    assert data["metric_id"] == "firm_style_nna"
    assert data["lineage"]["sql_model"] == "marts.mv_account_monthly_bridge"
    assert len(data["top_drivers"]) == 3
    assert "narrative" in data

    lin = client.get("/api/v1/metrics/firm_style_nna/lineage")
    assert lin.status_code == 200
    assert "raw.transaction_events" in lin.json()["source_tables"]

    assert client.get("/api/v1/metrics").status_code == 200
    assert len(client.get("/api/v1/metric-dictionary").json()) >= 15


def test_v1_segments_tie_to_overview():
    ov = client.get("/api/v1/overview?start_date=2026-07-01&end_date=2026-09-30").json()
    segs = client.get("/api/v1/segments?quarter_code=2026-Q3").json()
    assert len(segs) == 3
    seg_closing_sum = sum(Decimal(s["closing_assets_usd"]) for s in segs)
    assert seg_closing_sum == Decimal(ov["closing_assets_usd"])


def test_v1_advisors_pagination_sorting_and_drilldown():
    res = client.get("/api/v1/advisors?quarter_code=2026-Q3&page=1&page_size=5&sort_by=external_net_flows_usd&sort_dir=asc")
    assert res.status_code == 200
    body = res.json()
    assert len(body["items"]) == 5
    assert body["pagination"]["total_items"] == 40
    # ADV-001 (Story A) should be among top outflow advisors
    adv_id = body["items"][0]["advisor_id"]
    assert client.get(f"/api/v1/advisors/{adv_id}").status_code == 200
    assert client.get(f"/api/v1/advisors/{adv_id}/flows").status_code == 200
    assert client.get(f"/api/v1/advisors/{adv_id}/clients").status_code == 200


def test_v1_clients_accounts_and_transactions():
    cl_res = client.get("/api/v1/clients?page=1&page_size=5")
    assert cl_res.status_code == 200
    cl_id = cl_res.json()["items"][0]["client_id"]
    detail = client.get(f"/api/v1/clients/{cl_id}")
    assert detail.status_code == 200
    acct_id = detail.json()["accounts"][0]["account_id"]
    tx_res = client.get(f"/api/v1/accounts/{acct_id}/transactions")
    assert tx_res.status_code == 200
    assert client.get("/api/v1/transactions?page=1&page_size=10").status_code == 200
    assert client.get("/api/v1/flows").status_code == 200


def test_v1_reconciliation_detection_and_demo_ack():
    res = client.get("/api/v1/reconciliation")
    assert res.status_code == 200
    issues = res.json()
    types = {i["issue_type"] for i in issues}
    assert {"DUPLICATE_RECORD", "MISSING_TRANSACTION_AGGREGATE", "LATE_POSTED_TRANSFER", "CLASSIFICATION_MISMATCH"}.issubset(types)

    first_id = issues[0]["issue_id"]
    assert client.get(f"/api/v1/reconciliation/{first_id}").status_code == 200
    ack = client.post(f"/api/v1/reconciliation/{first_id}/acknowledge")
    assert ack.status_code == 200
    assert ack.json()["status"] == "ACKNOWLEDGED"


def test_v1_predefined_investigations():
    res = client.post(
        "/api/v1/investigations/run",
        json={"template_id": "top5_outflow_advisors", "quarter_code": "2026-Q3", "limit": 5},
    )
    assert res.status_code == 200
    assert len(res.json()["rows"]) == 5

    bad = client.post(
        "/api/v1/investigations/run",
        json={"template_id": "arbitrary_sql_injection", "quarter_code": "2026-Q3"},
    )
    assert bad.status_code == 404


def test_v1_phase05_investigations_and_drilldowns():
    # Constrained intent parser
    ok_intent = client.post(
        "/api/v1/investigations/parse-intent",
        json={"query": "Show the five advisors with the largest net outflows in Q3 2026."},
    )
    assert ok_intent.status_code == 200
    assert ok_intent.json()["supported"] is True
    assert ok_intent.json()["template_id"] == "top5_outflow_advisors"

    bad_intent = client.post(
        "/api/v1/investigations/parse-intent",
        json={"query": "DROP TABLE raw.accounts;"},
    )
    assert bad_intent.status_code == 200
    assert bad_intent.json()["supported"] is False

    # Saved investigation persistence
    saved = client.post(
        "/api/v1/investigations/saved",
        json={"name": "Q3 Outflow Audit", "template_id": "top5_outflow_advisors", "quarter_code": "2026-Q3"},
    )
    assert saved.status_code == 200
    assert len(client.get("/api/v1/investigations/saved").json()) >= 1

    # Metric evidence (Tab 4)
    ev = client.get("/api/v1/metrics/firm_style_nna/evidence?page=1&page_size=10")
    assert ev.status_code == 200
    assert len(ev.json()["items"]) == 10

    # Advisor summary -> Client -> Account details journey
    adv_id = client.get("/api/v1/advisors?page=1&page_size=1").json()["items"][0]["advisor_id"]
    summary = client.get(f"/api/v1/advisors/{adv_id}/summary").json()
    assert len(summary["account_distribution"]) >= 1
    cl_id = summary["top_clients"][0]["client_id"]
    acct_id = client.get(f"/api/v1/clients/{cl_id}").json()["accounts"][0]["account_id"]
    acct_det = client.get(f"/api/v1/accounts/{acct_id}/details")
    assert acct_det.status_code == 200
    assert len(acct_det.json()["valuations"]) >= 1


def test_v1_error_handling_and_sqli_resistance():
    assert client.get("/api/v1/overview?start_date=2026-10-01&end_date=2026-09-01").status_code == 422
    assert client.get("/api/v1/overview?advisor_id=not-a-uuid").status_code == 422
    assert client.get("/api/v1/metrics/does_not_exist").status_code == 404
    sqli = client.get("/api/v1/advisors?search=' OR 1=1;--")
    assert sqli.status_code == 200
    assert sqli.json()["items"] == []


def test_business_questions_sql_views():
    db_url = get_settings().sqlalchemy_database_url.replace("postgresql+psycopg://", "postgresql://")
    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            for view in [
                "marts.q_a_top5_outflow_advisors_q3_2026",
                "marts.q_b_segment_nna_growth_q3_2026",
                "marts.q_c_growth_attribution_q3_2026",
                "marts.q_d_adv001_client_outflows_q3_2026",
                "marts.q_e_fee_based_assets_q3_2026",
                "marts.q_f_top5_client_outflow_concentration_q3_2026",
                "marts.q_g_gross_vs_net_inflows_q3_2026",
                "marts.q_i_unreconciled_reported_accounts",
            ]:
                cur.execute(f"SELECT COUNT(*) FROM {view}")
                assert cur.fetchone()[0] >= 1


def test_v1_period_compare():
    r = client.get("/api/v1/period-compare?current_quarter=2026-Q3&prior_quarter=2026-Q2")
    assert r.status_code == 200
    body = r.json()
    assert body["current_quarter"] == "2026-Q3"
    assert body["prior_quarter"] == "2026-Q2"
    assert len(body["metrics"]) >= 4
    assert len(body["ranking_changes"]) >= 5


def test_v1_excel_export_ties_to_overview():
    import io
    from openpyxl import load_workbook

    overview = client.get("/api/v1/overview?start_date=2026-07-01&end_date=2026-09-30").json()
    r = client.get("/api/v1/exports/excel?quarter_code=2026-Q3")
    assert r.status_code == 200
    assert "spreadsheetml.sheet" in r.headers["content-type"]

    wb = load_workbook(io.BytesIO(r.content), data_only=False)
    expected_sheets = [
        "01 Executive Summary",
        "02 Asset Movement Bridge",
        "03 Advisor Performance",
        "04 Business Segments",
        "05 Client Flow Analysis",
        "06 Reconciliation Exceptions",
        "07 Source Data",
        "08 Metric Definitions",
        "09 Report Metadata",
    ]
    assert wb.sheetnames == expected_sheets

    # Verify live formula exists in Asset Movement Bridge sheet
    ws_bridge = wb["02 Asset Movement Bridge"]
    formulas = [
        cell.value
        for row in ws_bridge.iter_rows()
        for cell in row
        if isinstance(cell.value, str) and cell.value.startswith("=")
    ]
    assert len(formulas) >= 1

    # Verify Executive Summary Closing AUM matches Overview API
    ws_exec = wb["01 Executive Summary"]
    exec_values = {
        ws_exec.cell(row=row_idx, column=1).value: ws_exec.cell(row=row_idx, column=2).value
        for row_idx in range(1, ws_exec.max_row + 1)
    }
    expected_closing = float(overview["closing_assets_usd"])
    assert abs(float(exec_values["Closing Assets"]) - expected_closing) < 0.05


def test_v1_tableau_csv_exports_reconcile():
    import csv
    import io

    overview = client.get("/api/v1/overview?start_date=2026-07-01&end_date=2026-09-30").json()
    expected_closing = float(overview["closing_assets_usd"])

    for ds in [
        "advisor_performance",
        "asset_movement",
        "segment_performance",
        "monthly_flows",
        "reconciliation_exceptions",
    ]:
        r = client.get(f"/api/v1/exports/tableau/{ds}.csv?quarter_code=2026-Q3")
        assert r.status_code == 200
        rows = list(csv.DictReader(io.StringIO(r.text)))
        assert len(rows) >= 1
        if ds == "segment_performance":
            total_seg_closing = sum(float(row["closing_assets_usd"]) for row in rows)
            assert abs(total_seg_closing - expected_closing) < 0.05
        if ds == "reconciliation_exceptions":
            assert len(rows) >= 4

