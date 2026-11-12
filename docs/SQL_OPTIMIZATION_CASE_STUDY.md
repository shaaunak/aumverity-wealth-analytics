# AUMVERITY — SQL Optimization Case Study (`EXPLAIN (ANALYZE, BUFFERS)`)

## 1. Original Query & Measured Problem

Querying Q3 2026 Advisor AUM and Net New Assets directly from `raw.account_valuations` (`555,000` rows) joined to `raw.accounts`, `raw.advisors`, and `raw.transaction_events` (`67,397` rows):

```sql
EXPLAIN (ANALYZE, BUFFERS)
SELECT a.advisor_code,
       COUNT(DISTINCT v.account_id),
       SUM(v.total_aum_usd),
       SUM(t.net_amount) FILTER (WHERE t.nna_eligible)
FROM raw.account_valuations v
JOIN raw.accounts acct ON acct.account_id = v.account_id
JOIN raw.advisors a ON a.advisor_id = acct.advisor_id
LEFT JOIN raw.transaction_events t
    ON t.account_id = v.account_id
   AND t.effective_date BETWEEN '2026-07-01' AND '2026-09-30'
WHERE v.as_of_date = '2026-09-30'
GROUP BY a.advisor_code
ORDER BY 4 DESC;
```

**Measured Baseline Plan (PostgreSQL 16):**
- **Execution Time:** `143.589 ms` (`Planning Time: 8.404 ms`)
- **Bottlenecks:** `Seq Scan on transaction_events t` (`12,722` rows removed by filter), `Hash Right Join` expanding to `54,675` rows, and `Sort Method: external merge Disk: 2744kB` (`Buffers: shared hit=2091, temp read=343 written=344`).

## 2. Optimization Strategy

1. **Pre-Aggregation:** Materialized monthly account-level flows and valuations in `marts.mv_account_monthly_bridge` (`115,000` rows).
2. **Covering Index (`INCLUDE`):** Created `ix_mv_acct_bridge_end_date` on `(end_date, advisor_id) INCLUDE (account_id, actual_closing_assets_usd, firm_style_nna_usd)` and ran `ANALYZE` to enable an **Index-Only Scan** with zero heap fetches.

## 3. Optimized Query & Measured Result

```sql
EXPLAIN (ANALYZE, BUFFERS)
SELECT a.advisor_code,
       COUNT(DISTINCT b.account_id),
       SUM(b.actual_closing_assets_usd) FILTER (WHERE b.end_date = '2026-09-30'),
       SUM(b.firm_style_nna_usd)
FROM marts.mv_account_monthly_bridge b
JOIN raw.advisors a ON a.advisor_id = b.advisor_id
WHERE b.end_date BETWEEN '2026-07-01' AND '2026-09-30'
GROUP BY a.advisor_code
ORDER BY 4 DESC;
```

**Measured Optimized Plan:**
- **Execution Time:** `61.639 ms` (**2.33x faster**)
- **Scan Type:** `Index Only Scan using ix_mv_acct_bridge_end_date` (`Heap Fetches: 0`)
- **Buffers & Memory:** `Buffers: shared hit=11 read=139`, **`0` temp disk blocks** (eliminated `2,744 kB` disk sort).

## 4. Tradeoffs
- Materialized views require `REFRESH MATERIALIZED VIEW` after new ingestion runs and consume extra index storage (`ix_mv_acct_bridge_end_date`), which is well-justified for read-heavy analytical workloads.
