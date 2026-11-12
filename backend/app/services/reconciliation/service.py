from decimal import Decimal
import uuid

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schemas.analytics import ReconciliationIssueOut

SEVERITY_THRESHOLDS = {
    "CRITICAL_USD": Decimal("100000.00"),
    "HIGH_USD": Decimal("25000.00"),
}


def classify_severity(diff_usd: Decimal, issue_type: str) -> str:
    abs_diff = abs(diff_usd)
    if abs_diff >= SEVERITY_THRESHOLDS["CRITICAL_USD"]:
        return "CRITICAL"
    if abs_diff >= SEVERITY_THRESHOLDS["HIGH_USD"]:
        return "HIGH"
    if issue_type in ("CLASSIFICATION_MISMATCH", "LATE_POSTED_TRANSFER"):
        return "MEDIUM"
    return "LOW"


def discover_reconciliation_issues(db: Session) -> list[ReconciliationIssueOut]:
    issues: list[ReconciliationIssueOut] = []

    # Read acknowledged issue codes from raw.audit_events (demo-only acknowledgement)
    ack_rows = db.execute(
        text(
            """
            SELECT entity_id, created_at, actor
            FROM raw.audit_events
            WHERE entity_type = 'reconciliation_issue' AND action = 'ACKNOWLEDGED_DEMO'
            ORDER BY created_at DESC
            """
        )
    ).mappings().all()
    ack_map: dict[str, list[dict]] = {}
    for ar in ack_rows:
        ack_map.setdefault(ar["entity_id"], []).append(
            {"action": "ACKNOWLEDGED_DEMO", "actor": ar["actor"], "timestamp": ar["created_at"].isoformat()}
        )

    # 1. Duplicate record in reported_asset_snapshots
    dups = db.execute(
        text(
            """
            SELECT
                ras.account_id::TEXT,
                acct.account_number,
                ras.as_of_date,
                ras.record_hash,
                COUNT(*) AS dup_count,
                SUM(ras.reported_aum_usd) AS sum_reported_usd,
                MAX(ras.reported_aum_usd) AS expected_usd
            FROM raw.reported_asset_snapshots ras
            JOIN raw.accounts acct ON acct.account_id = ras.account_id
            GROUP BY ras.account_id, acct.account_number, ras.as_of_date, ras.record_hash
            HAVING COUNT(*) > 1
            """
        )
    ).mappings().all()
    for d in dups:
        diff = Decimal(str(d["sum_reported_usd"])) - Decimal(str(d["expected_usd"]))
        iid = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"dup:{d['account_id']}:{d['as_of_date']}"))
        audits = ack_map.get(iid, [])
        issues.append(
            ReconciliationIssueOut(
                issue_id=iid,
                issue_code="RECON-E1-DUPLICATE-FEED",
                issue_type="DUPLICATE_RECORD",
                severity=classify_severity(diff, "DUPLICATE_RECORD"),
                affected_period=d["as_of_date"].isoformat(),
                affected_scope=f"Account {d['account_number']}",
                expected_amount_usd=Decimal(str(d["expected_usd"])),
                reported_amount_usd=Decimal(str(d["sum_reported_usd"])),
                difference_usd=diff,
                likely_reason=f"Reporting feed ingested {d['dup_count']} identical rows with hash {d['record_hash'][:12]}...",
                detection_rule="GROUP BY account_id, as_of_date, record_hash HAVING COUNT(*) > 1",
                status="ACKNOWLEDGED" if audits else "OPEN",
                source_records=[{"account_number": d["account_number"], "record_hash": d["record_hash"]}],
                audit_history=audits,
            )
        )

    # 2. Reported AUM / NNA mismatch vs reconstructed bridge
    mismatches = db.execute(
        text(
            """
            SELECT DISTINCT ON (ras.account_id, ras.as_of_date)
                ras.account_id::TEXT,
                acct.account_number,
                ras.as_of_date,
                b.actual_closing_assets_usd AS expected_aum_usd,
                ras.reported_aum_usd
            FROM raw.reported_asset_snapshots ras
            JOIN raw.accounts acct ON acct.account_id = ras.account_id
            JOIN marts.mv_account_monthly_bridge b
                ON b.account_id = ras.account_id AND b.end_date = ras.as_of_date
            WHERE ras.reported_aum_usd <> b.actual_closing_assets_usd
               OR ras.reported_nna_usd <> b.firm_style_nna_usd
            """
        )
    ).mappings().all()
    for m in mismatches:
        diff = Decimal(str(m["reported_aum_usd"])) - Decimal(str(m["expected_aum_usd"]))
        iid = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"mis:{m['account_id']}:{m['as_of_date']}"))
        audits = ack_map.get(iid, [])
        issues.append(
            ReconciliationIssueOut(
                issue_id=iid,
                issue_code="RECON-E2-MISSING-TX-AGG",
                issue_type="MISSING_TRANSACTION_AGGREGATE",
                severity=classify_severity(diff, "MISSING_TRANSACTION_AGGREGATE"),
                affected_period=m["as_of_date"].isoformat(),
                affected_scope=f"Account {m['account_number']}",
                expected_amount_usd=Decimal(str(m["expected_aum_usd"])),
                reported_amount_usd=Decimal(str(m["reported_aum_usd"])),
                difference_usd=diff,
                likely_reason="Reported aggregate differs from ground-truth ledger and valuation snapshot.",
                detection_rule="reported_asset_snapshots.reported_aum_usd <> mv_account_monthly_bridge.actual_closing_assets_usd",
                status="ACKNOWLEDGED" if audits else "OPEN",
                source_records=[{"account_number": m["account_number"], "as_of_date": m["as_of_date"].isoformat()}],
                audit_history=audits,
            )
        )

    # 3. Late-posted transfers crossing month boundaries
    late_txs = db.execute(
        text(
            """
            SELECT
                t.event_id::TEXT,
                t.external_ref,
                acct.account_number,
                t.effective_date,
                t.posted_date,
                t.net_amount
            FROM staging.stg_transactions t
            JOIN raw.accounts acct ON acct.account_id = t.account_id
            WHERE t.is_late_posted = TRUE
              AND DATE_TRUNC('month', t.effective_date) <> DATE_TRUNC('month', t.posted_date)
            """
        )
    ).mappings().all()
    for lt in late_txs:
        amt = Decimal(str(lt["net_amount"]))
        iid = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"late:{lt['event_id']}"))
        audits = ack_map.get(iid, [])
        issues.append(
            ReconciliationIssueOut(
                issue_id=iid,
                issue_code="RECON-E3-LATE-POSTED",
                issue_type="LATE_POSTED_TRANSFER",
                severity="MEDIUM",
                affected_period=lt["effective_date"].isoformat(),
                affected_scope=f"Account {lt['account_number']}",
                expected_amount_usd=amt,
                reported_amount_usd=Decimal("0.00"),
                difference_usd=-amt,
                likely_reason=(
                    f"Transaction {lt['external_ref']} effective {lt['effective_date']} "
                    f"posted after period close on {lt['posted_date']}."
                ),
                detection_rule="DATE_TRUNC('month', effective_date) <> DATE_TRUNC('month', posted_date)",
                status="ACKNOWLEDGED" if audits else "OPEN",
                source_records=[{"external_ref": lt["external_ref"], "account_number": lt["account_number"]}],
                audit_history=audits,
            )
        )

    # 4. Advisor / Segment classification mismatch
    cls_rows = db.execute(
        text(
            """
            SELECT
                ras.reported_id::TEXT,
                acct.account_number,
                ras.as_of_date,
                ras.reported_aum_usd,
                acct.advisor_id::TEXT AS expected_advisor_id,
                ras.advisor_id::TEXT AS reported_advisor_id
            FROM raw.reported_asset_snapshots ras
            JOIN raw.accounts acct ON acct.account_id = ras.account_id
            WHERE ras.advisor_id <> acct.advisor_id OR ras.segment_id <> acct.segment_id
            """
        )
    ).mappings().all()
    for c in cls_rows:
        iid = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"cls:{c['reported_id']}"))
        audits = ack_map.get(iid, [])
        issues.append(
            ReconciliationIssueOut(
                issue_id=iid,
                issue_code="RECON-E4-CLASSIFICATION",
                issue_type="CLASSIFICATION_MISMATCH",
                severity="MEDIUM",
                affected_period=c["as_of_date"].isoformat(),
                affected_scope=f"Account {c['account_number']}",
                expected_amount_usd=Decimal(str(c["reported_aum_usd"])),
                reported_amount_usd=Decimal(str(c["reported_aum_usd"])),
                difference_usd=Decimal("0.00"),
                likely_reason="Reporting feed advisor_id or segment_id disagrees with authoritative account dimension.",
                detection_rule="reported_asset_snapshots.advisor_id <> accounts.advisor_id OR segment_id <> accounts.segment_id",
                status="ACKNOWLEDGED" if audits else "OPEN",
                source_records=[{"account_number": c["account_number"], "expected_advisor_id": c["expected_advisor_id"], "reported_advisor_id": c["reported_advisor_id"]}],
                audit_history=audits,
            )
        )

    return issues


def acknowledge_issue_demo(db: Session, issue_id: str, actor: str = "analyst_demo") -> ReconciliationIssueOut | None:
    issues = discover_reconciliation_issues(db)
    target = next((i for i in issues if i.issue_id == issue_id), None)
    if target is None:
        return None
    db.execute(
        text(
            """
            INSERT INTO raw.audit_events (audit_id, actor, action, entity_type, entity_id, payload_json)
            VALUES (:audit_id, :actor, 'ACKNOWLEDGED_DEMO', 'reconciliation_issue', :entity_id, CAST(:payload AS JSONB))
            """
        ),
        {
            "audit_id": str(uuid.uuid4()),
            "actor": actor,
            "entity_id": issue_id,
            "payload": '{"note": "Demo-only acknowledgement; reported accounting unaltered."}',
        },
    )
    db.commit()
    refreshed = discover_reconciliation_issues(db)
    return next((i for i in refreshed if i.issue_id == issue_id), None)
