-- =============================================================================
-- AUMVERITY — Phase 02: Auditable Asset Movement Bridge & 20 Financial Analytics
-- Calculation Version: v1.0.0 | Currency: USD | Convention: EOD Snapshot
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. Position-Level Market Attribution (Independent of Residual!)
--    Convention: End-of-Day snapshot; trades execute at period-end price, so
--    price-driven movement = SUM(beginning_qty * (ending_price - beginning_price)).
-- -----------------------------------------------------------------------------
CREATE MATERIALIZED VIEW IF NOT EXISTS marts.mv_position_market_attribution AS
WITH month_bounds AS (
    SELECT
        period_code,
        start_date,
        end_date,
        LAG(end_date) OVER (ORDER BY end_date) AS prior_end_date
    FROM raw.reporting_periods
    WHERE period_type = 'MONTHLY'
),
pos_pairs AS (
    SELECT
        mb.period_code,
        mb.start_date,
        mb.end_date,
        p0.account_id,
        p0.security_id,
        p0.quantity AS opening_qty,
        p0.market_price_usd AS opening_price_usd,
        sp1.close_price_usd AS closing_price_usd,
        (p0.quantity * (sp1.close_price_usd - p0.market_price_usd))::NUMERIC(18, 2) AS position_price_impact_usd
    FROM month_bounds mb
    JOIN raw.position_snapshots p0
        ON p0.as_of_date = mb.prior_end_date
    JOIN raw.security_prices sp1
        ON sp1.security_id = p0.security_id
       AND sp1.price_date = mb.end_date
    WHERE mb.prior_end_date IS NOT NULL
),
intra_month_trades AS (
    SELECT
        mb.period_code,
        t.account_id,
        (
            COALESCE(t.quantity, 0)
            * (sp1.close_price_usd - COALESCE(t.unit_price, sp1.close_price_usd))
        )::NUMERIC(18, 2) AS intra_period_price_impact_usd
    FROM month_bounds mb
    JOIN raw.transaction_events t
        ON t.effective_date BETWEEN mb.start_date AND mb.end_date
       AND t.security_id IS NOT NULL
       AND t.quantity IS NOT NULL
       AND t.event_type IN ('SECURITY_PURCHASE', 'SECURITY_SALE', 'DIVIDEND_REINVESTMENT', 'IN_KIND_ACQUISITION')
    JOIN raw.security_prices sp1
        ON sp1.security_id = t.security_id
       AND sp1.price_date = mb.end_date
    WHERE mb.prior_end_date IS NOT NULL
),
combined_mkt AS (
    SELECT period_code, account_id, position_price_impact_usd AS impact_usd FROM pos_pairs
    UNION ALL
    SELECT period_code, account_id, intra_period_price_impact_usd AS impact_usd FROM intra_month_trades
)
SELECT
    mb.period_code,
    mb.start_date,
    mb.end_date,
    cm.account_id,
    COALESCE(SUM(cm.impact_usd), 0)::NUMERIC(18, 2) AS price_driven_market_movement_usd
FROM combined_mkt cm
JOIN month_bounds mb ON mb.period_code = cm.period_code
GROUP BY mb.period_code, mb.start_date, mb.end_date, cm.account_id;

CREATE UNIQUE INDEX IF NOT EXISTS ix_mv_pos_mkt_attr_pk
    ON marts.mv_position_market_attribution (period_code, account_id);

-- -----------------------------------------------------------------------------
-- 2. Account-Month Auditable Asset Movement Bridge
--    Resolves historical advisor assignment via effective_from/effective_to.
--    Never conceals unexplained residual inside market movement.
-- -----------------------------------------------------------------------------
CREATE MATERIALIZED VIEW IF NOT EXISTS marts.mv_account_monthly_bridge AS
WITH month_bounds AS (
    SELECT
        period_code,
        start_date,
        end_date,
        LAG(end_date) OVER (ORDER BY end_date) AS prior_end_date
    FROM raw.reporting_periods
    WHERE period_type = 'MONTHLY'
),
acct_vals AS (
    SELECT
        mb.period_code,
        mb.start_date,
        mb.end_date,
        v1.account_id,
        -- Historical advisor & segment resolution as of period end_date
        COALESCE(aah.advisor_id, v1.advisor_id) AS advisor_id,
        COALESCE(ach.segment_id, v1.segment_id) AS segment_id,
        COALESCE(ach.account_type, acct.account_type) AS account_type,
        v0.total_aum_usd AS opening_assets_usd,
        v1.total_aum_usd AS actual_closing_assets_usd
    FROM month_bounds mb
    JOIN raw.account_valuations v1
        ON v1.as_of_date = mb.end_date
    JOIN raw.accounts acct
        ON acct.account_id = v1.account_id
    LEFT JOIN raw.account_valuations v0
        ON v0.account_id = v1.account_id
       AND v0.as_of_date = mb.prior_end_date
    LEFT JOIN raw.advisor_assignment_history aah
        ON aah.account_id = v1.account_id
       AND mb.end_date >= aah.effective_from
       AND (aah.effective_to IS NULL OR mb.end_date <= aah.effective_to)
    LEFT JOIN raw.account_classification_history ach
        ON ach.account_id = v1.account_id
       AND mb.end_date >= ach.effective_from
       AND (ach.effective_to IS NULL OR mb.end_date <= ach.effective_to)
    WHERE mb.prior_end_date IS NOT NULL
),
tx_agg AS (
    SELECT
        mb.period_code,
        t.account_id,
        COALESCE(SUM(t.net_amount) FILTER (
            WHERE t.event_type IN ('EXTERNAL_DEPOSIT', 'EXTERNAL_TRANSFER_IN', 'IN_KIND_ACQUISITION')
        ), 0)::NUMERIC(18, 2) AS gross_inflows_usd,
        COALESCE(SUM(ABS(t.net_amount)) FILTER (
            WHERE t.event_type IN ('EXTERNAL_WITHDRAWAL', 'EXTERNAL_TRANSFER_OUT')
        ), 0)::NUMERIC(18, 2) AS gross_outflows_usd,
        COALESCE(SUM(t.net_amount) FILTER (
            WHERE t.external_flow_eligible = TRUE
        ), 0)::NUMERIC(18, 2) AS external_net_flows_usd,
        COALESCE(SUM(t.net_amount) FILTER (
            WHERE t.event_type IN ('INTEREST_CREDITED', 'DIVIDEND_CREDITED')
        ), 0)::NUMERIC(18, 2) AS credited_income_usd,
        COALESCE(SUM(t.net_amount) FILTER (
            WHERE t.nna_eligible = TRUE
        ), 0)::NUMERIC(18, 2) AS firm_style_nna_usd,
        COALESCE(SUM(t.net_amount) FILTER (
            WHERE t.is_internal_transfer = TRUE
        ), 0)::NUMERIC(18, 2) AS internal_transfers_usd,
        (
            COALESCE(SUM(t.fee_amount), 0)
            + COALESCE(SUM(ABS(t.net_amount)) FILTER (WHERE t.event_type IN ('MANAGEMENT_FEE', 'COMMISSION')), 0)
        )::NUMERIC(18, 2) AS fees_and_commissions_usd
    FROM month_bounds mb
    JOIN raw.transaction_events t
        ON t.effective_date BETWEEN mb.start_date AND mb.end_date
    GROUP BY mb.period_code, t.account_id
)
SELECT
    av.period_code,
    av.start_date,
    av.end_date,
    av.account_id,
    av.advisor_id,
    av.segment_id,
    av.account_type,
    av.opening_assets_usd,
    COALESCE(tx.gross_inflows_usd, 0)::NUMERIC(18, 2) AS gross_inflows_usd,
    COALESCE(tx.gross_outflows_usd, 0)::NUMERIC(18, 2) AS gross_outflows_usd,
    COALESCE(tx.external_net_flows_usd, 0)::NUMERIC(18, 2) AS external_net_flows_usd,
    COALESCE(tx.credited_income_usd, 0)::NUMERIC(18, 2) AS credited_income_usd,
    COALESCE(tx.firm_style_nna_usd, 0)::NUMERIC(18, 2) AS firm_style_nna_usd,
    COALESCE(pma.price_driven_market_movement_usd, 0)::NUMERIC(18, 2) AS price_driven_market_movement_usd,
    COALESCE(tx.fees_and_commissions_usd, 0)::NUMERIC(18, 2) AS fees_and_commissions_usd,
    COALESCE(tx.internal_transfers_usd, 0)::NUMERIC(18, 2) AS explicit_other_adjustments_usd,
    CASE
        WHEN av.opening_assets_usd IS NULL THEN NULL
        ELSE (
            av.opening_assets_usd
            + COALESCE(tx.firm_style_nna_usd, 0)
            + COALESCE(pma.price_driven_market_movement_usd, 0)
            - COALESCE(tx.fees_and_commissions_usd, 0)
            + COALESCE(tx.internal_transfers_usd, 0)
        )::NUMERIC(18, 2)
    END AS expected_closing_assets_usd,
    av.actual_closing_assets_usd,
    CASE
        WHEN av.opening_assets_usd IS NULL THEN NULL
        ELSE (
            av.actual_closing_assets_usd - (
                av.opening_assets_usd
                + COALESCE(tx.firm_style_nna_usd, 0)
                + COALESCE(pma.price_driven_market_movement_usd, 0)
                - COALESCE(tx.fees_and_commissions_usd, 0)
                + COALESCE(tx.internal_transfers_usd, 0)
            )
        )::NUMERIC(18, 2)
    END AS unexplained_residual_usd
FROM acct_vals av
LEFT JOIN tx_agg tx
    ON tx.period_code = av.period_code AND tx.account_id = av.account_id
LEFT JOIN marts.mv_position_market_attribution pma
    ON pma.period_code = av.period_code AND pma.account_id = av.account_id;

CREATE UNIQUE INDEX IF NOT EXISTS ix_mv_acct_bridge_pk
    ON marts.mv_account_monthly_bridge (period_code, account_id);
CREATE INDEX IF NOT EXISTS ix_mv_acct_bridge_adv
    ON marts.mv_account_monthly_bridge (advisor_id, period_code);
CREATE INDEX IF NOT EXISTS ix_mv_acct_bridge_seg
    ON marts.mv_account_monthly_bridge (segment_id, period_code);
CREATE INDEX IF NOT EXISTS ix_mv_acct_bridge_end_date
    ON marts.mv_account_monthly_bridge (end_date, advisor_id)
    INCLUDE (account_id, actual_closing_assets_usd, firm_style_nna_usd);

-- -----------------------------------------------------------------------------
-- 3. Enterprise Monthly KPI Summary (All 20 Analytics Metrics)
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW marts.enterprise_monthly_kpis AS
WITH base AS (
    SELECT
        b.period_code,
        b.start_date,
        b.end_date,
        SUM(b.opening_assets_usd) AS opening_assets_usd,
        SUM(b.actual_closing_assets_usd) AS closing_assets_usd,
        SUM(b.gross_inflows_usd) AS gross_inflows_usd,
        SUM(b.gross_outflows_usd) AS gross_outflows_usd,
        SUM(b.external_net_flows_usd) AS external_net_flows_usd,
        SUM(b.firm_style_nna_usd) AS firm_style_nna_usd,
        SUM(b.price_driven_market_movement_usd) AS market_driven_movement_usd,
        SUM(b.fees_and_commissions_usd) AS fees_and_commissions_usd,
        SUM(b.explicit_other_adjustments_usd) AS explicit_other_adjustments_usd,
        SUM(b.unexplained_residual_usd) AS reconciliation_residual_usd,
        COALESCE(SUM(b.actual_closing_assets_usd) FILTER (WHERE b.account_type = 'Fee-based advisory'), 0) AS fee_based_assets_usd,
        COALESCE(SUM(b.firm_style_nna_usd) FILTER (WHERE b.account_type = 'Fee-based advisory'), 0) AS fee_based_asset_flows_usd,
        COUNT(*) FILTER (WHERE b.opening_assets_usd IS NULL) AS opened_accounts,
        COUNT(*) FILTER (WHERE b.actual_closing_assets_usd = 0 AND COALESCE(b.opening_assets_usd, 0) > 0) AS closed_accounts,
        COUNT(*) AS total_accounts
    FROM marts.mv_account_monthly_bridge b
    GROUP BY b.period_code, b.start_date, b.end_date
),
recon AS (
    SELECT
        as_of_date,
        COUNT(*) FILTER (WHERE is_corrupted_feed = FALSE) AS clean_reported_count,
        COUNT(*) AS total_reported_count
    FROM raw.reported_asset_snapshots
    GROUP BY as_of_date
)
SELECT
    base.period_code,
    base.start_date,
    base.end_date,
    base.opening_assets_usd::NUMERIC(18, 2),
    base.closing_assets_usd::NUMERIC(18, 2),
    (base.closing_assets_usd - base.opening_assets_usd)::NUMERIC(18, 2) AS total_asset_growth_usd,
    CASE WHEN base.opening_assets_usd > 0
         THEN ROUND(((base.closing_assets_usd - base.opening_assets_usd) / base.opening_assets_usd) * 100, 4)
         ELSE NULL END AS total_asset_growth_pct,
    base.external_net_flows_usd::NUMERIC(18, 2),
    base.firm_style_nna_usd::NUMERIC(18, 2),
    base.gross_inflows_usd::NUMERIC(18, 2),
    base.gross_outflows_usd::NUMERIC(18, 2),
    base.market_driven_movement_usd::NUMERIC(18, 2),
    base.fees_and_commissions_usd::NUMERIC(18, 2),
    base.explicit_other_adjustments_usd::NUMERIC(18, 2),
    base.fee_based_assets_usd::NUMERIC(18, 2),
    base.fee_based_asset_flows_usd::NUMERIC(18, 2),
    CASE WHEN base.opening_assets_usd > 0
         THEN ROUND((base.firm_style_nna_usd / base.opening_assets_usd) * 100, 4)
         ELSE NULL END AS period_nna_growth_rate_pct,
    SUM(base.firm_style_nna_usd) OVER (
        ORDER BY base.end_date ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
    )::NUMERIC(18, 2) AS rolling_3m_nna_usd,
    (base.firm_style_nna_usd - LAG(base.firm_style_nna_usd) OVER (ORDER BY base.end_date))::NUMERIC(18, 2) AS mom_nna_delta_usd,
    base.opened_accounts,
    base.closed_accounts,
    ROUND((base.closed_accounts::NUMERIC / NULLIF(base.total_accounts, 0)) * 100, 4) AS account_churn_rate_pct,
    -- Revenue-impact proxy (ESTIMATE ONLY: 85 bps annualized advisory fee proxy on fee-based assets)
    ROUND(base.fee_based_assets_usd * 0.0085, 2)::NUMERIC(18, 2) AS estimated_annual_fee_revenue_proxy_usd,
    base.reconciliation_residual_usd::NUMERIC(18, 2),
    CASE WHEN recon.total_reported_count > 0
         THEN ROUND((recon.clean_reported_count::NUMERIC / recon.total_reported_count) * 100, 2)
         ELSE NULL END AS reporting_completeness_pct
FROM base
LEFT JOIN recon ON recon.as_of_date = base.end_date
ORDER BY base.end_date;

-- -----------------------------------------------------------------------------
-- 4. Advisor Quarterly Performance & Rankings (with Outflow Concentration)
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW marts.advisor_quarterly_performance AS
WITH q_months AS (
    SELECT
        rp.period_code AS quarter_code,
        rp.start_date AS q_start,
        rp.end_date AS q_end,
        b.*
    FROM raw.reporting_periods rp
    JOIN marts.mv_account_monthly_bridge b
        ON b.end_date BETWEEN rp.start_date AND rp.end_date
    WHERE rp.period_type = 'QUARTERLY'
),
adv_q AS (
    SELECT
        qm.quarter_code,
        qm.q_start,
        qm.q_end,
        a.advisor_id,
        a.advisor_code,
        a.full_name AS advisor_name,
        bs.segment_name,
        COALESCE(SUM(qm.opening_assets_usd) FILTER (WHERE qm.start_date = qm.q_start), 0)::NUMERIC(18, 2) AS opening_assets_usd,
        COALESCE(SUM(qm.actual_closing_assets_usd) FILTER (WHERE qm.end_date = qm.q_end), 0)::NUMERIC(18, 2) AS closing_assets_usd,
        COALESCE(SUM(qm.gross_inflows_usd), 0)::NUMERIC(18, 2) AS gross_inflows_usd,
        COALESCE(SUM(qm.gross_outflows_usd), 0)::NUMERIC(18, 2) AS gross_outflows_usd,
        COALESCE(SUM(qm.external_net_flows_usd), 0)::NUMERIC(18, 2) AS external_net_flows_usd,
        COALESCE(SUM(qm.firm_style_nna_usd), 0)::NUMERIC(18, 2) AS firm_style_nna_usd,
        COALESCE(SUM(qm.price_driven_market_movement_usd), 0)::NUMERIC(18, 2) AS market_movement_usd,
        COALESCE(SUM(qm.fees_and_commissions_usd), 0)::NUMERIC(18, 2) AS fees_and_commissions_usd,
        COALESCE(SUM(qm.explicit_other_adjustments_usd), 0)::NUMERIC(18, 2) AS internal_transfers_usd,
        COALESCE(SUM(qm.unexplained_residual_usd), 0)::NUMERIC(18, 2) AS unexplained_residual_usd
    FROM q_months qm
    JOIN raw.advisors a ON a.advisor_id = qm.advisor_id
    JOIN raw.business_segments bs ON bs.segment_id = a.segment_id
    GROUP BY qm.quarter_code, qm.q_start, qm.q_end, a.advisor_id, a.advisor_code, a.full_name, bs.segment_name
)
SELECT
    *,
    (closing_assets_usd - opening_assets_usd)::NUMERIC(18, 2) AS aum_growth_usd,
    RANK() OVER (PARTITION BY quarter_code ORDER BY firm_style_nna_usd DESC) AS nna_rank,
    DENSE_RANK() OVER (PARTITION BY quarter_code ORDER BY external_net_flows_usd ASC) AS outflow_rank
FROM adv_q;

-- -----------------------------------------------------------------------------
-- 5. Segment Quarterly Contribution & Growth Attribution
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW marts.segment_quarterly_contribution AS
WITH q_seg AS (
    SELECT
        rp.period_code AS quarter_code,
        bs.segment_id,
        bs.segment_code,
        bs.segment_name,
        COALESCE(SUM(b.opening_assets_usd) FILTER (WHERE b.start_date = rp.start_date), 0)::NUMERIC(18, 2) AS opening_assets_usd,
        COALESCE(SUM(b.actual_closing_assets_usd) FILTER (WHERE b.end_date = rp.end_date), 0)::NUMERIC(18, 2) AS closing_assets_usd,
        COALESCE(SUM(b.firm_style_nna_usd), 0)::NUMERIC(18, 2) AS firm_style_nna_usd,
        COALESCE(SUM(b.external_net_flows_usd), 0)::NUMERIC(18, 2) AS external_net_flows_usd,
        COALESCE(SUM(b.price_driven_market_movement_usd), 0)::NUMERIC(18, 2) AS market_movement_usd,
        COALESCE(SUM(b.fees_and_commissions_usd), 0)::NUMERIC(18, 2) AS fees_and_commissions_usd
    FROM raw.reporting_periods rp
    JOIN marts.mv_account_monthly_bridge b
        ON b.end_date BETWEEN rp.start_date AND rp.end_date
    JOIN raw.business_segments bs ON bs.segment_id = b.segment_id
    WHERE rp.period_type = 'QUARTERLY'
    GROUP BY rp.period_code, bs.segment_id, bs.segment_code, bs.segment_name
)
SELECT
    *,
    (closing_assets_usd - opening_assets_usd)::NUMERIC(18, 2) AS total_growth_usd,
    CASE WHEN opening_assets_usd > 0
         THEN ROUND((firm_style_nna_usd / opening_assets_usd) * 100, 4)
         ELSE NULL END AS nna_growth_rate_pct,
    ROUND((closing_assets_usd / NULLIF(SUM(closing_assets_usd) OVER (PARTITION BY quarter_code), 0)) * 100, 2) AS segment_aum_share_pct
FROM q_seg;
