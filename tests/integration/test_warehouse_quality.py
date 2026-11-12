from decimal import Decimal

import psycopg
import pytest

from app.core.config import get_settings


def get_conn():
    settings = get_settings()
    db_url = settings.sqlalchemy_database_url.replace("postgresql+psycopg://", "postgresql://")
    return psycopg.connect(db_url)


@pytest.fixture(scope="module")
def db_conn():
    with get_conn() as conn:
        yield conn


def test_01_deterministic_seed_totals(db_conn):
    with db_conn.cursor() as cur:
        cur.execute("SELECT profile, seed, baseline_date, status FROM raw.ingestion_runs")
        runs = cur.fetchall()
        assert len(runs) == 1
        assert runs[0][0] == "demo"
        assert runs[0][1] == 10753
        assert runs[0][2].isoformat() == "2026-09-30"
        assert runs[0][3] == "COMPLETED"


def test_02_valid_account_and_advisor_references(db_conn):
    with db_conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*) FROM staging.stg_transactions
            WHERE dq_status <> 'VALID'
            """
        )
        assert cur.fetchone()[0] == 0


def test_03_internal_transfers_balance_to_zero(db_conn):
    with db_conn.cursor() as cur:
        cur.execute(
            """
            SELECT COALESCE(SUM(net_amount), 0)
            FROM raw.transaction_events
            WHERE is_internal_transfer = TRUE
            """
        )
        assert cur.fetchone()[0] == Decimal("0.00")

        cur.execute(
            """
            SELECT COUNT(*) FROM (
                SELECT transfer_group_id,
                       SUM(CASE WHEN leg_side = 'CREDIT' THEN amount_usd ELSE -amount_usd END) AS net_leg
                FROM raw.transaction_legs
                WHERE transfer_group_id IS NOT NULL
                GROUP BY transfer_group_id
                HAVING SUM(CASE WHEN leg_side = 'CREDIT' THEN amount_usd ELSE -amount_usd END) <> 0
            ) unbalanced
            """
        )
        assert cur.fetchone()[0] == 0


def test_04_security_trades_do_not_create_nna(db_conn):
    with db_conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*)
            FROM raw.transaction_events
            WHERE event_type IN ('SECURITY_PURCHASE', 'SECURITY_SALE', 'DIVIDEND_REINVESTMENT')
              AND (nna_eligible = TRUE OR external_flow_eligible = TRUE)
            """
        )
        assert cur.fetchone()[0] == 0


def test_05_no_unsupported_negative_quantities_or_cash(db_conn):
    with db_conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM raw.position_snapshots WHERE quantity < 0")
        assert cur.fetchone()[0] == 0
        cur.execute(
            "SELECT COUNT(*) FROM raw.account_cash_balances WHERE cash_balance_usd < 0 OR sweep_balance_usd < 0"
        )
        assert cur.fetchone()[0] == 0


def test_06_account_valuations_tie_to_cash_plus_securities(db_conn):
    with db_conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM staging.stg_account_valuations WHERE dq_status <> 'VALID'")
        assert cur.fetchone()[0] == 0


def test_07_required_reporting_periods_exist(db_conn):
    with db_conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM raw.reporting_periods WHERE period_type = 'MONTHLY'")
        assert cur.fetchone()[0] == 24
        cur.execute("SELECT COUNT(*) FROM raw.reporting_periods WHERE period_type = 'QUARTERLY'")
        assert cur.fetchone()[0] == 8
        cur.execute("SELECT MAX(end_date) FROM raw.reporting_periods")
        assert cur.fetchone()[0].isoformat() == "2026-09-30"


def test_08_business_stories_discoverable_via_sql(db_conn):
    with db_conn.cursor() as cur:
        # Story A: ADV-001 has negative external net flows in 2026-Q3
        cur.execute(
            """
            SELECT external_net_flows_usd
            FROM marts.advisor_level_flows
            WHERE advisor_code = 'ADV-001' AND period_code = '2026-Q3'
            """
        )
        adv1_flows = cur.fetchone()[0]
        assert adv1_flows < Decimal("0.00")

        # Story D: ADV-002 has strong positive NNA across multiple accounts in 2026-Q3
        cur.execute(
            """
            SELECT firm_style_nna_usd, active_accounts_with_flows
            FROM marts.advisor_level_flows
            WHERE advisor_code = 'ADV-002' AND period_code = '2026-Q3'
            """
        )
        adv2_nna, adv2_accts = cur.fetchone()
        assert adv2_nna > Decimal("500000.00")
        assert adv2_accts >= 10

        # Story B: Cash management sweep reductions exist
        cur.execute(
            """
            SELECT COUNT(*) FROM marts.account_level_cash_movement
            WHERE account_type = 'Cash management' AND sweep_delta_usd < 0
            """
        )
        assert cur.fetchone()[0] > 0

        # Story C: SDI has positive market appreciation in Q3 2026
        cur.execute(
            """
            SELECT SUM(market_appreciation_usd)
            FROM marts.segment_level_holdings
            WHERE segment_code = 'SDI' AND as_of_date BETWEEN '2026-07-01' AND '2026-09-30'
            """
        )
        assert cur.fetchone()[0] > Decimal("0.00")


def test_09_planted_anomalies_discoverable_via_sql(db_conn):
    with db_conn.cursor() as cur:
        # E1: Duplicate record in reported_asset_snapshots
        cur.execute(
            """
            SELECT COUNT(*) FROM staging.stg_reported_snapshots WHERE is_duplicate_record = TRUE
            """
        )
        assert cur.fetchone()[0] == 1

        # E2: Missing transaction in reporting aggregate (-250,000.00 variance)
        cur.execute(
            """
            SELECT COUNT(*)
            FROM marts.monthly_asset_snapshots mas
            JOIN raw.reported_asset_snapshots ras
              ON ras.account_id = mas.account_id AND ras.as_of_date = mas.as_of_date
            WHERE mas.as_of_date = '2026-09-30'
              AND (ras.reported_aum_usd - mas.ending_aum_usd) = -250000.00
            """
        )
        assert cur.fetchone()[0] == 1

        # E3: Late-posted transfer crossing month boundary
        cur.execute(
            """
            SELECT COUNT(*) FROM staging.stg_transactions
            WHERE is_late_posted = TRUE
              AND DATE_TRUNC('month', effective_date) <> DATE_TRUNC('month', posted_date)
            """
        )
        assert cur.fetchone()[0] == 2

        # E4: Incorrect advisor/segment classification in reported_asset_snapshots
        cur.execute(
            """
            SELECT COUNT(*)
            FROM raw.reported_asset_snapshots ras
            JOIN raw.accounts acct ON acct.account_id = ras.account_id
            WHERE ras.advisor_id <> acct.advisor_id OR ras.segment_id <> acct.segment_id
            """
        )
        assert cur.fetchone()[0] == 3
