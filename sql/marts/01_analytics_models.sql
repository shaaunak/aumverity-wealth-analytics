-- =============================================================================
-- AUMVERITY — Analytical Marts (CTEs & Window Functions)
-- =============================================================================

CREATE OR REPLACE VIEW marts.transaction_classifications AS
SELECT
    event_type,
    flow_classification,
    BOOL_OR(nna_eligible) AS nna_eligible,
    BOOL_OR(external_flow_eligible) AS external_flow_eligible,
    BOOL_OR(is_internal_transfer) AS is_internal_transfer,
    COUNT(*) AS event_count,
    COALESCE(SUM(gross_amount), 0)::NUMERIC(18, 2) AS total_gross_usd,
    COALESCE(SUM(fee_amount), 0)::NUMERIC(18, 2) AS total_fees_usd,
    COALESCE(SUM(net_amount), 0)::NUMERIC(18, 2) AS total_net_usd
FROM staging.stg_transactions
WHERE dq_status = 'VALID'
GROUP BY event_type, flow_classification
ORDER BY event_type;

CREATE OR REPLACE VIEW marts.monthly_asset_snapshots AS
WITH monthly_vals AS (
    SELECT
        av.account_id,
        av.advisor_id,
        av.segment_id,
        av.as_of_date,
        DATE_TRUNC('month', av.as_of_date)::DATE AS month_start,
        av.cash_value_usd,
        av.securities_value_usd,
        av.total_aum_usd AS ending_aum_usd,
        LAG(av.total_aum_usd) OVER (
            PARTITION BY av.account_id ORDER BY av.as_of_date
        ) AS beginning_aum_usd
    FROM staging.stg_account_valuations av
    JOIN raw.calendar c ON c.calendar_date = av.as_of_date
    WHERE c.is_month_end = TRUE
),
monthly_flows AS (
    SELECT
        t.account_id,
        DATE_TRUNC('month', t.effective_date)::DATE AS month_start,
        COALESCE(SUM(CASE WHEN t.flow_classification = 'EXTERNAL_INFLOW' THEN t.net_amount ELSE 0 END), 0) AS external_inflows_usd,
        COALESCE(SUM(CASE WHEN t.flow_classification = 'EXTERNAL_OUTFLOW' THEN ABS(t.net_amount) ELSE 0 END), 0) AS external_outflows_usd,
        COALESCE(SUM(CASE WHEN t.flow_classification = 'CREDITED_INCOME' THEN t.net_amount ELSE 0 END), 0) AS credited_income_usd,
        COALESCE(SUM(CASE WHEN t.nna_eligible THEN t.net_amount ELSE 0 END), 0) AS firm_style_nna_usd,
        COALESCE(SUM(CASE WHEN t.is_internal_transfer THEN t.net_amount ELSE 0 END), 0) AS internal_transfer_net_usd,
        COALESCE(SUM(t.fee_amount), 0) + COALESCE(SUM(CASE WHEN t.flow_classification = 'FEE_OR_COMMISSION' THEN ABS(t.net_amount) ELSE 0 END), 0) AS total_fees_usd
    FROM staging.stg_transactions t
    WHERE t.dq_status = 'VALID'
    GROUP BY t.account_id, DATE_TRUNC('month', t.effective_date)::DATE
)
SELECT
    mv.account_id,
    mv.advisor_id,
    mv.segment_id,
    mv.as_of_date,
    mv.month_start,
    mv.beginning_aum_usd,
    mv.cash_value_usd,
    mv.securities_value_usd,
    mv.ending_aum_usd,
    COALESCE(mf.external_inflows_usd, 0)::NUMERIC(18, 2) AS external_inflows_usd,
    COALESCE(mf.external_outflows_usd, 0)::NUMERIC(18, 2) AS external_outflows_usd,
    (COALESCE(mf.external_inflows_usd, 0) - COALESCE(mf.external_outflows_usd, 0))::NUMERIC(18, 2) AS external_net_flows_usd,
    COALESCE(mf.credited_income_usd, 0)::NUMERIC(18, 2) AS credited_income_usd,
    COALESCE(mf.firm_style_nna_usd, 0)::NUMERIC(18, 2) AS firm_style_nna_usd,
    COALESCE(mf.internal_transfer_net_usd, 0)::NUMERIC(18, 2) AS internal_transfer_net_usd,
    COALESCE(mf.total_fees_usd, 0)::NUMERIC(18, 2) AS total_fees_usd,
    CASE
        WHEN mv.beginning_aum_usd IS NULL THEN NULL
        ELSE (
            mv.ending_aum_usd
            - mv.beginning_aum_usd
            - COALESCE(mf.firm_style_nna_usd, 0)
            - COALESCE(mf.internal_transfer_net_usd, 0)
            + COALESCE(mf.total_fees_usd, 0)
        )::NUMERIC(18, 2)
    END AS market_appreciation_usd
FROM monthly_vals mv
LEFT JOIN monthly_flows mf
    ON mf.account_id = mv.account_id AND mf.month_start = mv.month_start;

CREATE OR REPLACE VIEW marts.daily_recent_asset_movements AS
WITH daily_vals AS (
    SELECT
        av.account_id,
        av.advisor_id,
        av.segment_id,
        av.as_of_date,
        av.cash_value_usd,
        av.securities_value_usd,
        av.total_aum_usd AS ending_aum_usd,
        LAG(av.total_aum_usd) OVER (
            PARTITION BY av.account_id ORDER BY av.as_of_date
        ) AS prior_aum_usd
    FROM staging.stg_account_valuations av
    JOIN raw.calendar c ON c.calendar_date = av.as_of_date
    WHERE c.is_90d_window = TRUE
),
daily_flows AS (
    SELECT
        t.account_id,
        t.effective_date AS as_of_date,
        COALESCE(SUM(CASE WHEN t.flow_classification = 'EXTERNAL_INFLOW' THEN t.net_amount ELSE 0 END), 0) AS external_inflows_usd,
        COALESCE(SUM(CASE WHEN t.flow_classification = 'EXTERNAL_OUTFLOW' THEN ABS(t.net_amount) ELSE 0 END), 0) AS external_outflows_usd,
        COALESCE(SUM(CASE WHEN t.nna_eligible THEN t.net_amount ELSE 0 END), 0) AS firm_style_nna_usd,
        COALESCE(SUM(CASE WHEN t.is_internal_transfer THEN t.net_amount ELSE 0 END), 0) AS internal_transfer_net_usd,
        COALESCE(SUM(t.fee_amount), 0) + COALESCE(SUM(CASE WHEN t.flow_classification = 'FEE_OR_COMMISSION' THEN ABS(t.net_amount) ELSE 0 END), 0) AS total_fees_usd
    FROM staging.stg_transactions t
    JOIN raw.calendar c ON c.calendar_date = t.effective_date
    WHERE c.is_90d_window = TRUE AND t.dq_status = 'VALID'
    GROUP BY t.account_id, t.effective_date
)
SELECT
    dv.account_id,
    dv.advisor_id,
    dv.segment_id,
    dv.as_of_date,
    dv.prior_aum_usd,
    dv.ending_aum_usd,
    COALESCE(df.external_inflows_usd, 0)::NUMERIC(18, 2) AS external_inflows_usd,
    COALESCE(df.external_outflows_usd, 0)::NUMERIC(18, 2) AS external_outflows_usd,
    COALESCE(df.firm_style_nna_usd, 0)::NUMERIC(18, 2) AS firm_style_nna_usd,
    COALESCE(df.internal_transfer_net_usd, 0)::NUMERIC(18, 2) AS internal_transfer_net_usd,
    COALESCE(df.total_fees_usd, 0)::NUMERIC(18, 2) AS total_fees_usd
FROM daily_vals dv
LEFT JOIN daily_flows df
    ON df.account_id = dv.account_id AND df.as_of_date = dv.as_of_date;

CREATE OR REPLACE VIEW marts.advisor_level_flows AS
SELECT
    a.advisor_id,
    a.advisor_code,
    a.full_name AS advisor_name,
    bs.segment_name,
    rp.period_code,
    rp.start_date,
    rp.end_date,
    COALESCE(SUM(CASE WHEN t.flow_classification = 'EXTERNAL_INFLOW' THEN t.net_amount ELSE 0 END), 0)::NUMERIC(18, 2) AS external_inflows_usd,
    COALESCE(SUM(CASE WHEN t.flow_classification = 'EXTERNAL_OUTFLOW' THEN ABS(t.net_amount) ELSE 0 END), 0)::NUMERIC(18, 2) AS external_outflows_usd,
    COALESCE(SUM(CASE WHEN t.external_flow_eligible THEN t.net_amount ELSE 0 END), 0)::NUMERIC(18, 2) AS external_net_flows_usd,
    COALESCE(SUM(CASE WHEN t.nna_eligible THEN t.net_amount ELSE 0 END), 0)::NUMERIC(18, 2) AS firm_style_nna_usd,
    COALESCE(SUM(CASE WHEN t.is_internal_transfer THEN t.net_amount ELSE 0 END), 0)::NUMERIC(18, 2) AS internal_transfer_net_usd,
    COUNT(DISTINCT t.account_id) AS active_accounts_with_flows
FROM raw.advisors a
JOIN raw.business_segments bs ON bs.segment_id = a.segment_id
CROSS JOIN raw.reporting_periods rp
LEFT JOIN staging.stg_transactions t
    ON t.advisor_id = a.advisor_id
    AND t.effective_date BETWEEN rp.start_date AND rp.end_date
    AND t.dq_status = 'VALID'
GROUP BY a.advisor_id, a.advisor_code, a.full_name, bs.segment_name, rp.period_code, rp.start_date, rp.end_date;

CREATE OR REPLACE VIEW marts.segment_level_holdings AS
SELECT
    bs.segment_id,
    bs.segment_code,
    bs.segment_name,
    mas.as_of_date,
    COUNT(DISTINCT mas.account_id) AS account_count,
    COALESCE(SUM(mas.beginning_aum_usd), 0)::NUMERIC(18, 2) AS beginning_aum_usd,
    COALESCE(SUM(mas.ending_aum_usd), 0)::NUMERIC(18, 2) AS ending_aum_usd,
    COALESCE(SUM(mas.firm_style_nna_usd), 0)::NUMERIC(18, 2) AS firm_style_nna_usd,
    COALESCE(SUM(mas.market_appreciation_usd), 0)::NUMERIC(18, 2) AS market_appreciation_usd,
    COALESCE(SUM(mas.total_fees_usd), 0)::NUMERIC(18, 2) AS total_fees_usd
FROM raw.business_segments bs
JOIN marts.monthly_asset_snapshots mas ON mas.segment_id = bs.segment_id
GROUP BY bs.segment_id, bs.segment_code, bs.segment_name, mas.as_of_date;

CREATE OR REPLACE VIEW marts.account_level_cash_movement AS
SELECT
    acb.account_id,
    acct.account_number,
    acct.account_type,
    acb.as_of_date,
    acb.cash_balance_usd,
    acb.sweep_balance_usd,
    (acb.cash_balance_usd + acb.sweep_balance_usd)::NUMERIC(18, 2) AS total_cash_usd,
    LAG(acb.sweep_balance_usd) OVER (
        PARTITION BY acb.account_id ORDER BY acb.as_of_date
    ) AS prior_sweep_balance_usd,
    (
        acb.sweep_balance_usd
        - LAG(acb.sweep_balance_usd) OVER (PARTITION BY acb.account_id ORDER BY acb.as_of_date)
    )::NUMERIC(18, 2) AS sweep_delta_usd
FROM raw.account_cash_balances acb
JOIN raw.accounts acct ON acct.account_id = acb.account_id;
