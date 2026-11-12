-- =============================================================================
-- AUMVERITY — Phase 02: Business Questions (A–I) Analytical Views
-- =============================================================================

-- Q-A: Which five advisors experienced the largest net outflows in Q3 2026?
CREATE OR REPLACE VIEW marts.q_a_top5_outflow_advisors_q3_2026 AS
SELECT
    advisor_id,
    advisor_code,
    advisor_name,
    segment_name,
    gross_inflows_usd,
    gross_outflows_usd,
    external_net_flows_usd,
    firm_style_nna_usd,
    outflow_rank
FROM marts.advisor_quarterly_performance
WHERE quarter_code = '2026-Q3'
ORDER BY external_net_flows_usd ASC
LIMIT 5;

-- Q-B: Which segment has the highest NNA growth in Q3 2026?
CREATE OR REPLACE VIEW marts.q_b_segment_nna_growth_q3_2026 AS
SELECT
    segment_id,
    segment_code,
    segment_name,
    opening_assets_usd,
    closing_assets_usd,
    firm_style_nna_usd,
    nna_growth_rate_pct,
    market_movement_usd,
    segment_aum_share_pct
FROM marts.segment_quarterly_contribution
WHERE quarter_code = '2026-Q3'
ORDER BY nna_growth_rate_pct DESC;

-- Q-C: Did client assets rise because of deposits (NNA) or investment performance?
CREATE OR REPLACE VIEW marts.q_c_growth_attribution_q3_2026 AS
SELECT
    '2026-Q3' AS quarter_code,
    SUM(opening_assets_usd) FILTER (WHERE period_code = '2026-07') AS opening_assets_usd,
    SUM(closing_assets_usd) FILTER (WHERE period_code = '2026-09') AS closing_assets_usd,
    SUM(firm_style_nna_usd) AS total_nna_usd,
    SUM(market_driven_movement_usd) AS total_market_movement_usd,
    SUM(fees_and_commissions_usd) AS total_fees_usd,
    ROUND(
        (SUM(firm_style_nna_usd) / NULLIF(SUM(firm_style_nna_usd) + SUM(market_driven_movement_usd), 0)) * 100,
        2
    ) AS nna_share_of_gross_growth_pct,
    ROUND(
        (SUM(market_driven_movement_usd) / NULLIF(SUM(firm_style_nna_usd) + SUM(market_driven_movement_usd), 0)) * 100,
        2
    ) AS market_share_of_gross_growth_pct
FROM marts.enterprise_monthly_kpis
WHERE period_code IN ('2026-07', '2026-08', '2026-09');

-- Q-D: Which clients account for most of ADV-001's outflows in Q3 2026?
CREATE OR REPLACE VIEW marts.q_d_adv001_client_outflows_q3_2026 AS
WITH adv_out AS (
    SELECT
        c.client_id,
        c.client_code,
        c.full_name AS client_name,
        SUM(ABS(t.net_amount)) AS client_outflows_usd
    FROM raw.transaction_events t
    JOIN raw.advisors a ON a.advisor_id = t.advisor_id
    JOIN raw.accounts acct ON acct.account_id = t.account_id
    JOIN raw.clients c ON c.client_id = acct.client_id
    WHERE a.advisor_code = 'ADV-001'
      AND t.effective_date BETWEEN '2026-07-01' AND '2026-09-30'
      AND t.event_type IN ('EXTERNAL_WITHDRAWAL', 'EXTERNAL_TRANSFER_OUT')
    GROUP BY c.client_id, c.client_code, c.full_name
)
SELECT
    client_id,
    client_code,
    client_name,
    client_outflows_usd::NUMERIC(18, 2),
    ROUND((client_outflows_usd / NULLIF(SUM(client_outflows_usd) OVER (), 0)) * 100, 2) AS share_of_advisor_outflows_pct
FROM adv_out
ORDER BY client_outflows_usd DESC;

-- Q-E: How did fee-based assets change in Q3 2026?
CREATE OR REPLACE VIEW marts.q_e_fee_based_assets_q3_2026 AS
SELECT
    period_code,
    fee_based_assets_usd,
    fee_based_asset_flows_usd,
    (fee_based_assets_usd - LAG(fee_based_assets_usd) OVER (ORDER BY end_date))::NUMERIC(18, 2) AS mom_fee_based_change_usd
FROM marts.enterprise_monthly_kpis
WHERE period_code IN ('2026-06', '2026-07', '2026-08', '2026-09')
ORDER BY end_date;

-- Q-F: What percentage of total Q3 2026 outflows is concentrated in the top five clients?
CREATE OR REPLACE VIEW marts.q_f_top5_client_outflow_concentration_q3_2026 AS
WITH client_out AS (
    SELECT
        c.client_id,
        c.client_code,
        SUM(ABS(t.net_amount)) AS outflows_usd
    FROM raw.transaction_events t
    JOIN raw.accounts acct ON acct.account_id = t.account_id
    JOIN raw.clients c ON c.client_id = acct.client_id
    WHERE t.effective_date BETWEEN '2026-07-01' AND '2026-09-30'
      AND t.event_type IN ('EXTERNAL_WITHDRAWAL', 'EXTERNAL_TRANSFER_OUT')
    GROUP BY c.client_id, c.client_code
),
ranked AS (
    SELECT
        *,
        ROW_NUMBER() OVER (ORDER BY outflows_usd DESC) AS rn,
        SUM(outflows_usd) OVER () AS enterprise_outflows_usd
    FROM client_out
)
SELECT
    SUM(outflows_usd) FILTER (WHERE rn <= 5)::NUMERIC(18, 2) AS top5_client_outflows_usd,
    MAX(enterprise_outflows_usd)::NUMERIC(18, 2) AS enterprise_outflows_usd,
    ROUND((SUM(outflows_usd) FILTER (WHERE rn <= 5) / NULLIF(MAX(enterprise_outflows_usd), 0)) * 100, 2) AS top5_concentration_pct
FROM ranked;

-- Q-G: How do gross inflows differ from net inflows in Q3 2026?
CREATE OR REPLACE VIEW marts.q_g_gross_vs_net_inflows_q3_2026 AS
SELECT
    period_code,
    gross_inflows_usd,
    gross_outflows_usd,
    external_net_flows_usd,
    firm_style_nna_usd,
    (firm_style_nna_usd - external_net_flows_usd)::NUMERIC(18, 2) AS credited_income_nna_diff_usd
FROM marts.enterprise_monthly_kpis
WHERE period_code IN ('2026-07', '2026-08', '2026-09')
ORDER BY end_date;

-- Q-H: Which advisor teams have positive AUM growth but negative NNA in Q3 2026?
CREATE OR REPLACE VIEW marts.q_h_pos_aum_neg_nna_advisors_q3_2026 AS
SELECT
    advisor_id,
    advisor_code,
    advisor_name,
    segment_name,
    opening_assets_usd,
    closing_assets_usd,
    aum_growth_usd,
    firm_style_nna_usd,
    market_movement_usd
FROM marts.advisor_quarterly_performance
WHERE quarter_code = '2026-Q3'
  AND aum_growth_usd > 0
  AND firm_style_nna_usd < 0
ORDER BY aum_growth_usd DESC;

-- Q-I: Which reported accounts do not reconcile as of 2026-09-30?
CREATE OR REPLACE VIEW marts.q_i_unreconciled_reported_accounts AS
WITH dedup_rep AS (
    SELECT
        ras.account_id,
        ras.as_of_date,
        COUNT(*) AS feed_row_count,
        MAX(ras.reported_aum_usd) AS reported_aum_usd,
        MAX(ras.reported_nna_usd) AS reported_nna_usd,
        MIN(ras.advisor_id::TEXT)::UUID AS reported_advisor_id,
        MIN(ras.segment_id::TEXT)::UUID AS reported_segment_id
    FROM raw.reported_asset_snapshots ras
    WHERE ras.as_of_date = '2026-09-30'
    GROUP BY ras.account_id, ras.as_of_date
)
SELECT
    acct.account_id,
    acct.account_number,
    dr.as_of_date,
    dr.feed_row_count,
    b.actual_closing_assets_usd AS expected_aum_usd,
    dr.reported_aum_usd,
    (dr.reported_aum_usd - b.actual_closing_assets_usd)::NUMERIC(18, 2) AS aum_diff_usd,
    b.firm_style_nna_usd AS expected_nna_usd,
    dr.reported_nna_usd,
    (dr.reported_nna_usd - b.firm_style_nna_usd)::NUMERIC(18, 2) AS nna_diff_usd,
    (dr.reported_advisor_id <> acct.advisor_id) AS advisor_mismatch,
    (dr.reported_segment_id <> acct.segment_id) AS segment_mismatch
FROM dedup_rep dr
JOIN raw.accounts acct ON acct.account_id = dr.account_id
JOIN marts.mv_account_monthly_bridge b
    ON b.account_id = dr.account_id AND b.end_date = dr.as_of_date
WHERE dr.feed_row_count > 1
   OR dr.reported_aum_usd <> b.actual_closing_assets_usd
   OR dr.reported_nna_usd <> b.firm_style_nna_usd
   OR dr.reported_advisor_id <> acct.advisor_id
   OR dr.reported_segment_id <> acct.segment_id;
