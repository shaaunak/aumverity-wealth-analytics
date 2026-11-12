-- =============================================================================
-- AUMVERITY — Automated Reconciliation & Anomaly Discovery Queries
-- =============================================================================

-- 1. Duplicate record in reporting feed (Story E1)
SELECT
    feed_source,
    account_id,
    as_of_date,
    record_hash,
    COUNT(*) AS duplicate_count,
    SUM(reported_aum_usd) AS sum_reported_aum_usd,
    MAX(reported_aum_usd) AS expected_aum_usd
FROM raw.reported_asset_snapshots
GROUP BY feed_source, account_id, as_of_date, record_hash
HAVING COUNT(*) > 1;

-- 2. Ground-truth vs. Reported NNA / AUM mismatch (Story E2: missing transaction)
SELECT
    mas.account_id,
    mas.as_of_date,
    mas.firm_style_nna_usd AS expected_nna_usd,
    ras.reported_nna_usd,
    (ras.reported_nna_usd - mas.firm_style_nna_usd) AS nna_variance_usd,
    mas.ending_aum_usd AS expected_aum_usd,
    ras.reported_aum_usd,
    (ras.reported_aum_usd - mas.ending_aum_usd) AS aum_variance_usd
FROM marts.monthly_asset_snapshots mas
JOIN (
    SELECT DISTINCT ON (account_id, as_of_date)
        account_id, as_of_date, reported_nna_usd, reported_aum_usd
    FROM raw.reported_asset_snapshots
    ORDER BY account_id, as_of_date, reported_id
) ras ON ras.account_id = mas.account_id AND ras.as_of_date = mas.as_of_date
WHERE ras.reported_nna_usd <> mas.firm_style_nna_usd
   OR ras.reported_aum_usd <> mas.ending_aum_usd;

-- 3. Late-posted transfers crossing month/quarter boundaries (Story E3)
SELECT
    t.event_id,
    t.external_ref,
    t.account_id,
    t.event_type,
    t.effective_date,
    t.posted_date,
    (t.posted_date - t.effective_date) AS lag_days,
    t.net_amount
FROM staging.stg_transactions t
WHERE t.is_late_posted = TRUE
  AND DATE_TRUNC('month', t.effective_date) <> DATE_TRUNC('month', t.posted_date);

-- 4. Incorrect advisor or segment classification in reporting feed (Story E4)
SELECT
    ras.reported_id,
    ras.account_id,
    ras.as_of_date,
    acct.advisor_id AS expected_advisor_id,
    ras.advisor_id AS reported_advisor_id,
    acct.segment_id AS expected_segment_id,
    ras.segment_id AS reported_segment_id
FROM raw.reported_asset_snapshots ras
JOIN raw.accounts acct ON acct.account_id = ras.account_id
WHERE ras.advisor_id <> acct.advisor_id
   OR ras.segment_id <> acct.segment_id;
