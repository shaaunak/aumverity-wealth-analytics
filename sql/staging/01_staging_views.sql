-- =============================================================================
-- AUMVERITY — Staging Layer Views & Validations
-- =============================================================================

CREATE OR REPLACE VIEW staging.stg_transactions AS
SELECT
    te.event_id,
    te.external_ref,
    te.account_id,
    te.advisor_id,
    te.segment_id,
    te.event_type,
    te.effective_date,
    te.posted_date,
    (te.posted_date - te.effective_date) AS posting_lag_days,
    (te.posted_date > te.effective_date) AS is_late_posted,
    te.trade_timestamp,
    te.security_id,
    te.quantity,
    te.unit_price,
    te.gross_amount,
    te.fee_amount,
    te.net_amount,
    te.currency,
    te.nna_eligible,
    te.external_flow_eligible,
    te.is_internal_transfer,
    te.counterparty_account_id,
    te.transfer_group_id,
    te.ingestion_run_id,
    CASE
        WHEN te.event_type IN ('EXTERNAL_DEPOSIT', 'EXTERNAL_TRANSFER_IN', 'IN_KIND_ACQUISITION')
            THEN 'EXTERNAL_INFLOW'
        WHEN te.event_type IN ('EXTERNAL_WITHDRAWAL', 'EXTERNAL_TRANSFER_OUT')
            THEN 'EXTERNAL_OUTFLOW'
        WHEN te.event_type IN ('INTEREST_CREDITED', 'DIVIDEND_CREDITED')
            THEN 'CREDITED_INCOME'
        WHEN te.event_type = 'DIVIDEND_REINVESTMENT'
            THEN 'REINVESTMENT_NON_NNA'
        WHEN te.event_type = 'INTERNAL_ACCOUNT_TRANSFER'
            THEN 'INTERNAL_TRANSFER'
        WHEN te.event_type IN ('SECURITY_PURCHASE', 'SECURITY_SALE')
            THEN 'SECURITY_TRADE'
        WHEN te.event_type IN ('MANAGEMENT_FEE', 'COMMISSION')
            THEN 'FEE_OR_COMMISSION'
        WHEN te.event_type = 'CORPORATE_ACTION'
            THEN 'CORPORATE_ACTION'
        ELSE 'ACCOUNT_LIFECYCLE'
    END AS flow_classification,
    CASE
        WHEN te.account_id IS NULL OR te.advisor_id IS NULL OR te.segment_id IS NULL THEN 'INVALID_NULL_FK'
        WHEN te.gross_amount IS NULL OR te.net_amount IS NULL THEN 'INVALID_NULL_AMOUNT'
        WHEN te.currency <> 'USD' THEN 'INVALID_CURRENCY'
        WHEN te.quantity IS NOT NULL AND te.quantity < 0 AND te.event_type NOT IN ('SECURITY_SALE', 'CORPORATE_ACTION') THEN 'INVALID_NEGATIVE_QTY'
        ELSE 'VALID'
    END AS dq_status
FROM raw.transaction_events te;

CREATE OR REPLACE VIEW staging.stg_account_valuations AS
SELECT
    av.valuation_id,
    av.account_id,
    av.as_of_date,
    av.period_granularity,
    av.cash_value_usd,
    av.securities_value_usd,
    av.total_aum_usd,
    av.advisor_id,
    av.segment_id,
    (av.total_aum_usd - (av.cash_value_usd + av.securities_value_usd)) AS balance_tie_diff_usd,
    CASE
        WHEN av.total_aum_usd = (av.cash_value_usd + av.securities_value_usd) THEN 'VALID'
        ELSE 'BALANCE_MISMATCH'
    END AS dq_status
FROM raw.account_valuations av;

CREATE OR REPLACE VIEW staging.stg_reported_snapshots AS
WITH ranked AS (
    SELECT
        ras.*,
        ROW_NUMBER() OVER (
            PARTITION BY ras.feed_source, ras.account_id, ras.as_of_date, ras.record_hash
            ORDER BY ras.reported_id
        ) AS dup_rank
    FROM raw.reported_asset_snapshots ras
)
SELECT
    reported_id,
    feed_source,
    account_id,
    advisor_id,
    segment_id,
    as_of_date,
    reported_aum_usd,
    reported_inflows_usd,
    reported_outflows_usd,
    reported_nna_usd,
    reported_market_change_usd,
    reported_fees_usd,
    record_hash,
    is_corrupted_feed,
    ingestion_run_id,
    (dup_rank > 1) AS is_duplicate_record
FROM ranked;
