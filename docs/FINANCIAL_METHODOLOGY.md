# AUMVERITY — Financial Methodology

> **Important:** All financial calculations are deterministic SQL/Decimal computations. LLMs are never used for arithmetic or attribution.

## 1. Fundamental Asset Movement Identity

For any account, advisor book, segment, or firm total over a reporting period $[t_0, t_1]$:

$$\text{Ending AUM}_{t_1} = \text{Beginning AUM}_{t_0} + \text{Firm-Style NNA} + \text{Market Appreciation} - \text{Fees \& Commissions}$$

Where:
- **Beginning AUM ($t_0$):** End-of-period (EOP) market value snapshot as of the prior business date.
- **Ending AUM ($t_1$):** End-of-period (EOP) market value snapshot as of the current business date.
- **No Fabricated Residual:** Market appreciation is computed from position/market return attribution. Any difference between $(\text{Ending AUM} - \text{Beginning AUM})$ and $(\text{NNA} + \text{Market Appreciation} - \text{Fees})$ is surfaced explicitly as an **Unreconciled Variance** in the Reconciliation Center—never disguised as market movement.

## 2. External Net Flows vs. Firm-Style Net New Assets (NNA)

| Metric | Definition |
|--------|-----------|
| **External Net Flows** | $\text{External Client Inflows} - \text{External Client Outflows}$ (wires, ACH, ACAT-in, ACAT-out, check deposits/withdrawals). |
| **Firm-Style NNA** | $\text{Eligible Client Inflows} + \text{Credited Interest \& Dividends} + \text{Eligible Asset Acquisitions} - \text{Eligible Outflows}$. |
| **Internal Transfers** | Movements between two accounts within the firm. **Net to $0.00$ at the firm level**; tracked separately at the account and advisor level so advisor book transfers are visible without inflating firm NNA. |

## 3. Anti-Double-Counting Rules

1. **Dividends & Reinvestments:** Credited cash dividends/interest enter NNA once when credited; subsequent automatic dividend reinvestment (DRIP) security purchases are internal cash-to-security conversions and do **not** add to NNA a second time.
2. **Security Trades:** Buys and sells within an account are portfolio reallocations, not inflows/outflows.
3. **Fees & Commissions:** Advisory fees, custody fees, and commissions are tracked in a dedicated fee bucket and subtracted explicitly in the bridge, never netted silently into flows or market performance.
4. **Currency:** Starting implementation is **USD-only**. FX attribution is excluded until multi-currency accounting is implemented.
