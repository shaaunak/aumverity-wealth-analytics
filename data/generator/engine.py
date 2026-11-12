from __future__ import annotations

import calendar as pycal
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
import hashlib
import json
from pathlib import Path
import time
import uuid

import numpy as np
import psycopg

from app.core.config import get_settings
from data.generator.config import (
    ACCOUNT_TYPES,
    ASSET_CLASSES,
    CLIENT_TIERS,
    PROFILES,
    REGIONS,
    RISK_PROFILES,
    SEGMENTS,
    SYNTHETIC_SECURITIES,
    ProfileConfig,
)

NAMESPACE_BASE = uuid.UUID("7f3c9b10-5c4a-4e8a-9b2d-1a2b3c4d5e6f")


def det_uuid(seed: int, kind: str, idx: int | str) -> uuid.UUID:
    return uuid.uuid5(NAMESPACE_BASE, f"{seed}:{kind}:{idx}")


def q2(val: float | Decimal) -> Decimal:
    return Decimal(str(val)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def q6(val: float | Decimal) -> Decimal:
    return Decimal(str(val)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


def month_ends_between(start: date, end: date) -> list[date]:
    res: list[date] = []
    y, m = start.year, start.month
    while True:
        last_day = pycal.monthrange(y, m)[1]
        d = date(y, m, last_day)
        if d > end:
            break
        if d >= start:
            res.append(d)
        m += 1
        if m > 12:
            m = 1
            y += 1
    return res


def copy_rows(
    cur: psycopg.Cursor,
    table: str,
    columns: list[str],
    rows: list[tuple],
) -> None:
    if not rows:
        return
    cols_sql = ", ".join(columns)
    with cur.copy(f"COPY {table} ({cols_sql}) FROM STDIN") as copy:
        for row in rows:
            copy.write_row(row)


@dataclass
class GenerationSummary:
    run_id: uuid.UUID
    profile: str
    seed: int
    baseline_date: date
    row_counts: dict[str, int]
    manifest: dict
    duration_seconds: float


def run_generation(profile_name: str, seed: int) -> GenerationSummary:
    t0 = time.perf_counter()
    if profile_name not in PROFILES:
        raise ValueError(f"Unknown profile '{profile_name}'. Choose from {list(PROFILES.keys())}.")

    cfg: ProfileConfig = PROFILES[profile_name]
    rng = np.random.default_rng(seed)
    settings = get_settings()

    # Convert SQLAlchemy URL to standard psycopg libpq URL
    db_url = settings.sqlalchemy_database_url.replace("postgresql+psycopg://", "postgresql://")

    baseline_date = cfg.baseline_date  # 2026-09-30
    history_start = date(2024, 10, 1)
    window_90d_start = baseline_date - timedelta(days=cfg.daily_window_days - 1)  # 2026-07-03

    run_id = det_uuid(seed, f"run:{profile_name}", 1)
    now_utc = datetime(2026, 9, 30, 23, 59, 0, tzinfo=UTC)

    # 1. Calendar & Reporting Periods
    all_dates: list[date] = []
    cur_d = history_start
    while cur_d <= baseline_date:
        all_dates.append(cur_d)
        cur_d += timedelta(days=1)

    month_ends = set(month_ends_between(history_start, baseline_date))
    quarter_ends = {d for d in month_ends if d.month in (3, 6, 9, 12)}

    calendar_rows = []
    for d in all_dates:
        dow = d.weekday()  # 0=Mon..6=Sun
        calendar_rows.append((
            d,
            d.year,
            (d.month - 1) // 3 + 1,
            d.month,
            dow,
            dow < 5,
            d in month_ends,
            d in quarter_ends,
            d >= window_90d_start,
        ))

    reporting_period_rows = []
    for me in sorted(month_ends):
        p_start = date(me.year, me.month, 1)
        p_code = f"{me.year}-{me.month:02d}"
        reporting_period_rows.append((
            det_uuid(seed, "period_m", p_code),
            p_code,
            "MONTHLY",
            p_start,
            me,
            True,
        ))
    for qe in sorted(quarter_ends):
        q_num = (qe.month - 1) // 3 + 1
        q_start_month = (q_num - 1) * 3 + 1
        p_start = date(qe.year, q_start_month, 1)
        p_code = f"{qe.year}-Q{q_num}"
        reporting_period_rows.append((
            det_uuid(seed, "period_q", p_code),
            p_code,
            "QUARTERLY",
            p_start,
            qe,
            True,
        ))

    # 2. Segments, Asset Classes, Securities
    segment_rows = []
    segment_ids: dict[str, uuid.UUID] = {}
    for code, name, desc in SEGMENTS:
        sid = det_uuid(seed, "segment", code)
        segment_ids[code] = sid
        segment_rows.append((sid, code, name, desc))

    asset_class_rows = []
    asset_class_ids: dict[str, uuid.UUID] = {}
    for code, name, is_cash in ASSET_CLASSES:
        acid = det_uuid(seed, "asset_class", code)
        asset_class_ids[code] = acid
        asset_class_rows.append((acid, code, name, is_cash))

    security_rows = []
    securities_meta: list[dict] = []
    for ticker, name, ac_code, is_ce, base_p, drift, vol in SYNTHETIC_SECURITIES:
        sec_id = det_uuid(seed, "security", ticker)
        security_rows.append((
            sec_id,
            ticker,
            name,
            asset_class_ids[ac_code],
            is_ce,
            q6(base_p),
            q6(drift),
            q6(vol),
        ))
        securities_meta.append({
            "security_id": sec_id,
            "ticker": ticker,
            "ac_code": ac_code,
            "is_ce": is_ce,
            "base_price": float(base_p),
            "drift": float(drift),
            "vol": float(vol),
        })

    # Snapshot dates: monthly outside 90d window, daily inside 90d window
    snapshot_dates = sorted(
        {d for d in month_ends if d < window_90d_start}
        | {d for d in all_dates if d >= window_90d_start}
    )

    # Generate synthetic daily security prices across all dates, with Q3 2026 strong equity/tech rally for Story C
    price_map: dict[tuple[uuid.UUID, date], Decimal] = {}
    security_price_rows = []
    dt = 1.0 / 252.0
    for sec in securities_meta:
        sec_id = sec["security_id"]
        p = sec["base_price"]
        prev_p = p
        for d in all_dates:
            if d.weekday() < 5:
                if sec["is_ce"]:
                    ret = sec["drift"] * dt
                else:
                    drift = sec["drift"]
                    # Story C: boost synthetic equity/tech ETFs in Q3 2026
                    if d >= date(2026, 7, 1) and sec["ticker"] in ("SYN-EQ-TECH", "SYN-ETF-AI", "SYN-ETF-SPX"):
                        drift += 0.45
                    ret = float(drift * dt + sec["vol"] * np.sqrt(dt) * rng.normal())
                p = max(1.0, p * (1.0 + ret))
                daily_ret = (p - prev_p) / prev_p if prev_p > 0 else 0.0
                prev_p = p
            else:
                daily_ret = 0.0

            p_dec = q6(p)
            price_map[(sec_id, d)] = p_dec
            if d in snapshot_dates or d in month_ends:
                security_price_rows.append((
                    det_uuid(seed, "sec_price", f"{sec['ticker']}:{d.isoformat()}"),
                    sec_id,
                    d,
                    p_dec,
                    Decimal(f"{daily_ret:.8f}"),
                ))

    # 3. Advisors (ADV-001 = Story A outflow advisor, ADV-002 = Story D high-growth advisor)
    advisor_rows = []
    advisors_meta: list[dict] = []
    seg_codes = [s[0] for s in SEGMENTS]
    for i in range(cfg.num_advisors):
        adv_code = f"ADV-{i + 1:03d}"
        adv_id = det_uuid(seed, "advisor", adv_code)
        if i in (0, 1):
            seg_code = "ALWM"
        else:
            seg_code = seg_codes[int(rng.choice(len(seg_codes), p=[0.50, 0.25, 0.25]))]
        region = REGIONS[i % len(REGIONS)]
        hire_date = date(2016 + (i % 8), (i % 12) + 1, 1)
        full_name = f"Advisor {i + 1:03d} ({region})"
        advisor_rows.append((
            adv_id,
            adv_code,
            full_name,
            segment_ids[seg_code],
            region,
            hire_date,
            "ACTIVE",
            now_utc,
        ))
        advisors_meta.append({
            "advisor_id": adv_id,
            "advisor_code": adv_code,
            "segment_code": seg_code,
            "segment_id": segment_ids[seg_code],
        })

    # 4. Households, Clients, Accounts
    household_rows = []
    households_meta: list[dict] = []
    for i in range(cfg.num_households):
        hh_code = f"HH-{i + 1:05d}"
        hh_id = det_uuid(seed, "household", hh_code)
        seg_code = seg_codes[int(rng.choice(len(seg_codes), p=[0.50, 0.30, 0.20]))]
        household_rows.append((
            hh_id,
            hh_code,
            f"Household {i + 1:05d}",
            segment_ids[seg_code],
            now_utc,
        ))
        households_meta.append({"household_id": hh_id, "segment_code": seg_code})

    client_rows = []
    clients_meta: list[dict] = []
    for i in range(cfg.num_clients):
        cl_code = f"CL-{i + 1:05d}"
        cl_id = det_uuid(seed, "client", cl_code)
        hh = households_meta[i % len(households_meta)]
        tier = CLIENT_TIERS[int(rng.choice(len(CLIENT_TIERS), p=[0.60, 0.30, 0.10]))]
        risk = RISK_PROFILES[int(rng.integers(0, len(RISK_PROFILES)))]
        onb_offset = int(rng.integers(0, 365 * 4))
        onb_date = date(2021, 1, 1) + timedelta(days=onb_offset)
        client_rows.append((
            cl_id,
            cl_code,
            hh["household_id"],
            f"Client {i + 1:05d}",
            tier,
            risk,
            onb_date,
            "ACTIVE",
            now_utc,
        ))
        clients_meta.append({
            "client_id": cl_id,
            "client_code": cl_code,
            "household_id": hh["household_id"],
            "segment_code": hh["segment_code"],
            "tier": tier,
        })

    # Group advisors by segment for assignment
    advisors_by_seg: dict[str, list[dict]] = {s: [] for s in seg_codes}
    for adv in advisors_meta:
        advisors_by_seg[adv["segment_code"]].append(adv)

    account_rows = []
    adv_assign_rows = []
    acct_class_rows = []
    accounts_meta: list[dict] = []

    story_a_accounts: list[dict] = []
    story_b_accounts: list[dict] = []
    story_c_accounts: list[dict] = []
    story_d_accounts: list[dict] = []

    for i in range(cfg.num_accounts):
        acct_num = f"ACCT-{i + 1:06d}"
        acct_id = det_uuid(seed, "account", acct_num)
        cl = clients_meta[i % len(clients_meta)]
        seg_code = cl["segment_code"]

        # Pin first 25 accounts to ADV-001 (Story A) and next 25 to ADV-002 (Story D)
        if i < 25:
            adv = advisors_meta[0]
            seg_code = "ALWM"
        elif 25 <= i < 50:
            adv = advisors_meta[1]
            seg_code = "ALWM"
        else:
            seg_advs = advisors_by_seg[seg_code]
            adv = seg_advs[int(rng.integers(0, len(seg_advs)))]

        if seg_code == "SDI":
            acct_type = ACCOUNT_TYPES[int(rng.choice([1, 2], p=[0.7, 0.3]))]
        elif seg_code == "WPW":
            acct_type = ACCOUNT_TYPES[2]
        else:
            acct_type = ACCOUNT_TYPES[int(rng.choice(len(ACCOUNT_TYPES), p=[0.55, 0.15, 0.15, 0.15]))]

        opened = history_start
        # Story D: 15 accounts under ADV-002 opened in Q3 2026
        if 35 <= i < 50:
            opened = date(2026, 7, 6 + (i - 35))

        account_rows.append((
            acct_id,
            acct_num,
            cl["client_id"],
            cl["household_id"],
            segment_ids[seg_code],
            adv["advisor_id"],
            acct_type,
            opened,
            None,
            "USD",
            "OPEN",
            now_utc,
        ))
        adv_assign_rows.append((
            det_uuid(seed, "adv_assign", f"{acct_num}:0"),
            cl["client_id"],
            acct_id,
            adv["advisor_id"],
            opened,
            None,
            True,
            "INITIAL_ONBOARDING",
            now_utc,
        ))
        acct_class_rows.append((
            det_uuid(seed, "acct_class", f"{acct_num}:0"),
            acct_id,
            segment_ids[seg_code],
            adv["advisor_id"],
            acct_type,
            opened,
            None,
            True,
            now_utc,
        ))

        meta = {
            "account_id": acct_id,
            "account_number": acct_num,
            "client_id": cl["client_id"],
            "advisor_id": adv["advisor_id"],
            "advisor_code": adv["advisor_code"],
            "segment_id": segment_ids[seg_code],
            "segment_code": seg_code,
            "account_type": acct_type,
            "opened_date": opened,
            "tier": cl["tier"],
        }
        accounts_meta.append(meta)

        if i < 6:
            story_a_accounts.append(meta)
        if acct_type == "Cash management" and len(story_b_accounts) < 35:
            story_b_accounts.append(meta)
        if seg_code == "SDI" and len(story_c_accounts) < 40:
            story_c_accounts.append(meta)
        if 25 <= i < 50:
            story_d_accounts.append(meta)

    # 5. Simulate Account Balances, Holdings, and ~60,000+ Financial Events
    tx_rows = []
    leg_rows = []
    fee_rows = []
    income_rows = []
    cash_bal_rows = []
    pos_snap_rows = []
    acct_val_rows = []
    reported_rows = []

    event_seq = 0

    def next_event_id() -> tuple[uuid.UUID, str]:
        nonlocal event_seq
        event_seq += 1
        return det_uuid(seed, "tx", event_seq), f"TX-{seed}-{event_seq:07d}"

    # Initialize starting state for each account at history_start
    acct_state: dict[uuid.UUID, dict] = {}
    tech_secs = [s["security_id"] for s in securities_meta if s["ticker"] in ("SYN-EQ-TECH", "SYN-ETF-AI", "SYN-ETF-SPX")]
    core_secs = [s["security_id"] for s in securities_meta if not s["is_ce"]]

    for meta in accounts_meta:
        aid = meta["account_id"]
        if meta["opened_date"] > history_start:
            # New Q3 2026 account starts at $0 until funded
            acct_state[aid] = {"cash": Decimal("0.00"), "sweep": Decimal("0.00"), "pos": {}, "basis": {}}
            continue

        base_aum = float(rng.lognormal(mean=12.0, sigma=0.75))
        if meta["tier"] == "Ultra High Net Worth":
            base_aum *= 2.5
        # Ensure Story A departing accounts hold ample initial liquidity for large Q3 outflows
        if meta in story_a_accounts:
            base_aum = max(base_aum, 15_000_000.0)
            cash = q2(base_aum * 0.30)
            sweep = q2(base_aum * 0.10)
            investable = base_aum * 0.60
            chosen_secs = list(rng.choice(core_secs, size=3, replace=False))
            pos = {}
            basis = {}
            alloc = investable / len(chosen_secs)
            for sid in chosen_secs:
                px = price_map[(sid, history_start)]
                qty = q6(Decimal(str(alloc)) / px)
                pos[sid] = qty
                basis[sid] = q2(qty * px)
        elif meta["account_type"] == "Cash management":
            cash = q2(base_aum * 0.25)
            sweep = q2(base_aum * 0.75)
            pos = {}
            basis = {}
        else:
            cash = q2(base_aum * 0.08)
            sweep = q2(base_aum * 0.07)
            investable = base_aum * 0.85
            chosen_secs = tech_secs[:2] if meta["segment_code"] == "SDI" else list(rng.choice(core_secs, size=3, replace=False))
            pos = {}
            basis = {}
            alloc = investable / len(chosen_secs)
            for sid in chosen_secs:
                px = price_map[(sid, history_start)]
                qty = q6(Decimal(str(alloc)) / px)
                pos[sid] = qty
                basis[sid] = q2(qty * px)
        acct_state[aid] = {"cash": cash, "sweep": sweep, "pos": pos, "basis": basis}

    # Pre-plan Story A, B, D, E events on specific dates
    story_a_dates = [date(2026, 7, 15), date(2026, 7, 29), date(2026, 8, 12), date(2026, 8, 26), date(2026, 9, 10), date(2026, 9, 18)]
    story_b_dates = [date(2026, 6, 15), date(2026, 7, 20), date(2026, 8, 18), date(2026, 9, 14)]
    late_posted_transfer_ref: dict | None = None

    # Monthly NNA accumulator per account for reported_asset_snapshots
    monthly_nna_acc: dict[tuple[uuid.UUID, int, int], Decimal] = {}
    monthly_inflow_acc: dict[tuple[uuid.UUID, int, int], Decimal] = {}
    monthly_outflow_acc: dict[tuple[uuid.UUID, int, int], Decimal] = {}
    monthly_fee_acc: dict[tuple[uuid.UUID, int, int], Decimal] = {}

    def record_tx(
        meta: dict,
        event_type: str,
        eff_date: date,
        post_date: date,
        gross_amt: Decimal,
        fee_amt: Decimal,
        net_amt: Decimal,
        nna_eligible: bool,
        ext_eligible: bool,
        is_internal: bool,
        sec_id: uuid.UUID | None = None,
        qty: Decimal | None = None,
        unit_px: Decimal | None = None,
        counterparty_id: uuid.UUID | None = None,
        transfer_group_id: uuid.UUID | None = None,
        desc: str = "",
    ) -> uuid.UUID:
        ev_id, ext_ref = next_event_id()
        ts = datetime(eff_date.year, eff_date.month, eff_date.day, 16, 0, 0, tzinfo=UTC)
        tx_rows.append((
            ev_id, ext_ref, meta["account_id"], meta["advisor_id"], meta["segment_id"],
            event_type, eff_date, post_date, ts, sec_id, qty, unit_px,
            gross_amt, fee_amt, net_amt, "USD",
            nna_eligible, ext_eligible, is_internal, counterparty_id, transfer_group_id,
            desc, run_id, now_utc,
        ))
        ym_key = (meta["account_id"], eff_date.year, eff_date.month)
        if nna_eligible:
            monthly_nna_acc[ym_key] = monthly_nna_acc.get(ym_key, Decimal("0.00")) + net_amt
        if event_type in ("EXTERNAL_DEPOSIT", "EXTERNAL_TRANSFER_IN", "IN_KIND_ACQUISITION"):
            monthly_inflow_acc[ym_key] = monthly_inflow_acc.get(ym_key, Decimal("0.00")) + net_amt
        if event_type in ("EXTERNAL_WITHDRAWAL", "EXTERNAL_TRANSFER_OUT"):
            monthly_outflow_acc[ym_key] = monthly_outflow_acc.get(ym_key, Decimal("0.00")) + abs(net_amt)
        if fee_amt > 0 or event_type in ("MANAGEMENT_FEE", "COMMISSION"):
            f_val = fee_amt if fee_amt > 0 else abs(net_amt)
            monthly_fee_acc[ym_key] = monthly_fee_acc.get(ym_key, Decimal("0.00")) + f_val
        return ev_id

    # Step through each snapshot_date chronologically
    prev_snap_date = history_start
    events_per_step = max(1, cfg.target_events // len(snapshot_dates))

    for step_idx, snap_d in enumerate(snapshot_dates):
        # 1. Story-driven & background events on snap_d
        # Story A: Major outflows on ADV-001 in Q3 2026
        for idx_a, d_a in enumerate(story_a_dates):
            if prev_snap_date < d_a <= snap_d and idx_a < len(story_a_accounts):
                meta = story_a_accounts[idx_a]
                st = acct_state[meta["account_id"]]
                amt = q2(2500000.0 + idx_a * 200000.0)
                if st["cash"] < amt:
                    st["cash"] += amt  # ensure funded prior to outflow
                st["cash"] -= amt
                ev_id = record_tx(
                    meta, "EXTERNAL_TRANSFER_OUT", d_a, d_a, amt, Decimal("0.00"), -amt,
                    True, True, False, desc="Story A: Large client departure outflow"
                )
                leg_rows.append((
                    det_uuid(seed, "leg", f"{ev_id}:1"), ev_id, None, meta["account_id"],
                    "DEBIT", "CASH", None, None, amt, d_a, d_a
                ))

        # Story B: Sweep-to-external rate-driven outflows
        for d_b in story_b_dates:
            if prev_snap_date < d_b <= snap_d:
                for meta in story_b_accounts[:12]:
                    st = acct_state[meta["account_id"]]
                    out_amt = q2(min(float(st["sweep"]) * 0.35, 125000.0))
                    if out_amt > Decimal("1000.00"):
                        st["sweep"] -= out_amt
                        ev_id = record_tx(
                            meta, "EXTERNAL_WITHDRAWAL", d_b, d_b, out_amt, Decimal("0.00"), -out_amt,
                            True, True, False, desc="Story B: Sweep-to-external rate shift"
                        )
                        leg_rows.append((
                            det_uuid(seed, "leg", f"{ev_id}:1"), ev_id, None, meta["account_id"],
                            "DEBIT", "CASH", None, None, out_amt, d_b, d_b
                        ))

        # Story D: High-growth advisor ADV-002 diversified new client inflows in Q3 2026
        if snap_d >= date(2026, 7, 1) and snap_d.weekday() < 5 and step_idx % 3 == 0:
            for meta in story_d_accounts[:8]:
                st = acct_state[meta["account_id"]]
                in_amt = q2(float(rng.uniform(45000, 180000)))
                st["cash"] += in_amt
                ev_id = record_tx(
                    meta, "EXTERNAL_DEPOSIT", snap_d, snap_d, in_amt, Decimal("0.00"), in_amt,
                    True, True, False, desc="Story D: Diversified new client inflow"
                )
                leg_rows.append((
                    det_uuid(seed, "leg", f"{ev_id}:1"), ev_id, None, meta["account_id"],
                    "CREDIT", "CASH", None, None, in_amt, snap_d, snap_d
                ))

        # Story E3: Late-posted internal transfer crossing 2026-09-30 quarter boundary
        if prev_snap_date < date(2026, 9, 29) <= snap_d:
            src_meta = accounts_meta[60]
            dst_meta = accounts_meta[61]
            t_amt = Decimal("150000.00")
            if acct_state[src_meta["account_id"]]["cash"] < t_amt:
                acct_state[src_meta["account_id"]]["cash"] += t_amt
            acct_state[src_meta["account_id"]]["cash"] -= t_amt
            acct_state[dst_meta["account_id"]]["cash"] += t_amt
            tg_id = det_uuid(seed, "tg_late", 1)
            eff_d = date(2026, 9, 29)
            post_d = date(2026, 10, 2)
            ev1 = record_tx(
                src_meta, "INTERNAL_ACCOUNT_TRANSFER", eff_d, post_d, t_amt, Decimal("0.00"), -t_amt,
                False, False, True, counterparty_id=dst_meta["account_id"], transfer_group_id=tg_id,
                desc="Story E3: Late-posted internal transfer (debit)"
            )
            ev2 = record_tx(
                dst_meta, "INTERNAL_ACCOUNT_TRANSFER", eff_d, post_d, t_amt, Decimal("0.00"), t_amt,
                False, False, True, counterparty_id=src_meta["account_id"], transfer_group_id=tg_id,
                desc="Story E3: Late-posted internal transfer (credit)"
            )
            leg_rows.append((det_uuid(seed, "leg", f"{ev1}:1"), ev1, tg_id, src_meta["account_id"], "DEBIT", "CASH", None, None, t_amt, eff_d, post_d))
            leg_rows.append((det_uuid(seed, "leg", f"{ev2}:1"), ev2, tg_id, dst_meta["account_id"], "CREDIT", "CASH", None, None, t_amt, eff_d, post_d))
            late_posted_transfer_ref = {
                "transfer_group_id": str(tg_id),
                "source_account": src_meta["account_number"],
                "dest_account": dst_meta["account_number"],
                "effective_date": eff_d.isoformat(),
                "posted_date": post_d.isoformat(),
                "amount_usd": "150000.00",
            }

        # Regular synthetic activity to reach ~60,000 events in demo profile
        sample_indices = rng.integers(0, len(accounts_meta), size=events_per_step)
        for idx_acct in sample_indices:
            meta = accounts_meta[int(idx_acct)]
            if meta["opened_date"] > snap_d:
                continue
            st = acct_state[meta["account_id"]]
            roll = float(rng.random())

            if roll < 0.22:
                # External deposit
                amt = q2(float(rng.uniform(2500, 35000)))
                st["cash"] += amt
                ev_id = record_tx(meta, "EXTERNAL_DEPOSIT", snap_d, snap_d, amt, Decimal("0.00"), amt, True, True, False)
                leg_rows.append((det_uuid(seed, "leg", f"{ev_id}:1"), ev_id, None, meta["account_id"], "CREDIT", "CASH", None, None, amt, snap_d, snap_d))
            elif roll < 0.38:
                # External withdrawal (only if cash available)
                if st["cash"] > Decimal("3000.00"):
                    amt = q2(min(float(st["cash"]) * 0.25, float(rng.uniform(1500, 20000))))
                    st["cash"] -= amt
                    ev_id = record_tx(meta, "EXTERNAL_WITHDRAWAL", snap_d, snap_d, amt, Decimal("0.00"), -amt, True, True, False)
                    leg_rows.append((det_uuid(seed, "leg", f"{ev_id}:1"), ev_id, None, meta["account_id"], "DEBIT", "CASH", None, None, amt, snap_d, snap_d))
            elif roll < 0.54:
                # Security purchase
                sec_id = core_secs[int(rng.integers(0, len(core_secs)))]
                px = price_map[(sec_id, snap_d)]
                if st["cash"] > px * Decimal("5"):
                    qty = q6(min(Decimal("25"), (st["cash"] * Decimal("0.20")) / px))
                    cost = q2(qty * px)
                    comm = Decimal("0.00") if meta["account_type"] == "Fee-based advisory" else Decimal("4.95")
                    if st["cash"] >= cost + comm and qty > 0:
                        st["cash"] -= (cost + comm)
                        st["pos"][sec_id] = st["pos"].get(sec_id, Decimal("0.000000")) + qty
                        st["basis"][sec_id] = st["basis"].get(sec_id, Decimal("0.00")) + cost
                        ev_id = record_tx(
                            meta, "SECURITY_PURCHASE", snap_d, snap_d, cost, comm, -(cost + comm),
                            False, False, False, sec_id=sec_id, qty=qty, unit_px=px
                        )
                        leg_rows.append((det_uuid(seed, "leg", f"{ev_id}:1"), ev_id, None, meta["account_id"], "CREDIT", "SECURITY", sec_id, qty, cost, snap_d, snap_d))
                        leg_rows.append((det_uuid(seed, "leg", f"{ev_id}:2"), ev_id, None, meta["account_id"], "DEBIT", "CASH", None, None, cost + comm, snap_d, snap_d))
            elif roll < 0.66 and st["pos"]:
                # Security sale
                sec_id = next(iter(st["pos"].keys()))
                held_qty = st["pos"][sec_id]
                if held_qty > Decimal("1.000000"):
                    sell_qty = q6(held_qty * Decimal("0.25"))
                    px = price_map[(sec_id, snap_d)]
                    proceeds = q2(sell_qty * px)
                    st["pos"][sec_id] = held_qty - sell_qty
                    st["cash"] += proceeds
                    ev_id = record_tx(
                        meta, "SECURITY_SALE", snap_d, snap_d, proceeds, Decimal("0.00"), proceeds,
                        False, False, False, sec_id=sec_id, qty=-sell_qty, unit_px=px
                    )
                    leg_rows.append((det_uuid(seed, "leg", f"{ev_id}:1"), ev_id, None, meta["account_id"], "DEBIT", "SECURITY", sec_id, -sell_qty, proceeds, snap_d, snap_d))
                    leg_rows.append((det_uuid(seed, "leg", f"{ev_id}:2"), ev_id, None, meta["account_id"], "CREDIT", "CASH", None, None, proceeds, snap_d, snap_d))
            elif roll < 0.78:
                # Dividend or Interest credited
                is_div = bool(st["pos"]) and rng.random() < 0.6
                amt = q2(float(rng.uniform(40, 650)))
                st["cash"] += amt
                etype = "DIVIDEND_CREDITED" if is_div else "INTEREST_CREDITED"
                sec_id = next(iter(st["pos"].keys())) if is_div else None
                ev_id = record_tx(meta, etype, snap_d, snap_d, amt, Decimal("0.00"), amt, True, False, False, sec_id=sec_id)
                income_rows.append((det_uuid(seed, "inc", ev_id), ev_id, meta["account_id"], sec_id, etype, snap_d, snap_d, amt, False))
                # Optional DRIP reinvestment (does NOT add to NNA!)
                if is_div and sec_id is not None and st["cash"] >= amt:
                    px = price_map[(sec_id, snap_d)]
                    qty = q6(amt / px)
                    st["cash"] -= amt
                    st["pos"][sec_id] = st["pos"].get(sec_id, Decimal("0.000000")) + qty
                    st["basis"][sec_id] = st["basis"].get(sec_id, Decimal("0.00")) + amt
                    drip_id = record_tx(
                        meta, "DIVIDEND_REINVESTMENT", snap_d, snap_d, amt, Decimal("0.00"), Decimal("0.00"),
                        False, False, False, sec_id=sec_id, qty=qty, unit_px=px
                    )
                    income_rows.append((det_uuid(seed, "inc", drip_id), drip_id, meta["account_id"], sec_id, "DIVIDEND_REINVESTMENT", snap_d, snap_d, amt, True))
            elif roll < 0.88:
                # Management fee or commission
                fee_amt = q2(float(rng.uniform(25, 450)))
                if st["cash"] >= fee_amt:
                    st["cash"] -= fee_amt
                    ftype = "MANAGEMENT_FEE" if meta["account_type"] == "Fee-based advisory" else "COMMISSION"
                    ev_id = record_tx(meta, ftype, snap_d, snap_d, fee_amt, fee_amt, -fee_amt, False, False, False)
                    fee_rows.append((det_uuid(seed, "fee", ev_id), ev_id, meta["account_id"], meta["advisor_id"], ftype, snap_d, snap_d, fee_amt))
            elif roll < 0.94:
                # Internal transfer between two accounts (linked double-entry legs, net=0 at firm level)
                dst_idx = (int(idx_acct) + 1) % len(accounts_meta)
                dst_meta = accounts_meta[dst_idx]
                if dst_meta["opened_date"] <= snap_d and st["cash"] > Decimal("5000.00"):
                    t_amt = q2(min(float(st["cash"]) * 0.2, 15000.0))
                    st["cash"] -= t_amt
                    acct_state[dst_meta["account_id"]]["cash"] += t_amt
                    tg_id = det_uuid(seed, "tg", f"{step_idx}:{event_seq}")
                    ev1 = record_tx(meta, "INTERNAL_ACCOUNT_TRANSFER", snap_d, snap_d, t_amt, Decimal("0.00"), -t_amt, False, False, True, counterparty_id=dst_meta["account_id"], transfer_group_id=tg_id)
                    ev2 = record_tx(dst_meta, "INTERNAL_ACCOUNT_TRANSFER", snap_d, snap_d, t_amt, Decimal("0.00"), t_amt, False, False, True, counterparty_id=meta["account_id"], transfer_group_id=tg_id)
                    leg_rows.append((det_uuid(seed, "leg", f"{ev1}:1"), ev1, tg_id, meta["account_id"], "DEBIT", "CASH", None, None, t_amt, snap_d, snap_d))
                    leg_rows.append((det_uuid(seed, "leg", f"{ev2}:1"), ev2, tg_id, dst_meta["account_id"], "CREDIT", "CASH", None, None, t_amt, snap_d, snap_d))
            else:
                # Lifecycle / Corporate action / In-kind acquisition / Advisor reassignment
                sub_roll = float(rng.random())
                if sub_roll < 0.4:
                    sec_id = core_secs[0]
                    px = price_map[(sec_id, snap_d)]
                    qty = q6(Decimal("10.000000"))
                    val = q2(qty * px)
                    st["pos"][sec_id] = st["pos"].get(sec_id, Decimal("0.000000")) + qty
                    st["basis"][sec_id] = st["basis"].get(sec_id, Decimal("0.00")) + val
                    record_tx(meta, "IN_KIND_ACQUISITION", snap_d, snap_d, val, Decimal("0.00"), val, True, True, False, sec_id=sec_id, qty=qty, unit_px=px)
                elif sub_roll < 0.7:
                    record_tx(meta, "CORPORATE_ACTION", snap_d, snap_d, Decimal("0.00"), Decimal("0.00"), Decimal("0.00"), False, False, False)
                else:
                    record_tx(meta, "ADVISOR_REASSIGNMENT", snap_d, snap_d, Decimal("0.00"), Decimal("0.00"), Decimal("0.00"), False, False, False)

        # 2. Record EOP snapshots for snap_d
        gran = "DAILY" if snap_d >= window_90d_start else "MONTHLY"
        is_me = snap_d in month_ends

        for meta in accounts_meta:
            aid = meta["account_id"]
            st = acct_state[aid]
            cash_val = q2(st["cash"] + st["sweep"])
            sec_val = Decimal("0.00")
            for sec_id, qty in st["pos"].items():
                if qty <= 0:
                    continue
                px = price_map[(sec_id, snap_d)]
                mv = q2(qty * px)
                sec_val += mv
                # Store position_snapshots at month-ends and baseline_date to keep DB compact
                if is_me or snap_d == baseline_date:
                    pos_snap_rows.append((
                        det_uuid(seed, "pos", f"{aid}:{sec_id}:{snap_d.isoformat()}"),
                        aid, sec_id, snap_d, qty, px, mv, st["basis"].get(sec_id, mv),
                    ))
            total_aum = q2(cash_val + sec_val)
            if is_me or snap_d == baseline_date:
                cash_bal_rows.append((
                    det_uuid(seed, "cash_bal", f"{aid}:{snap_d.isoformat()}"),
                    aid, snap_d, q2(st["cash"]), q2(st["sweep"]),
                ))
            acct_val_rows.append((
                det_uuid(seed, "val", f"{aid}:{snap_d.isoformat()}"),
                aid, snap_d, gran, cash_val, sec_val, total_aum,
                meta["advisor_id"], meta["segment_id"],
            ))

            # Populate clean reported_asset_snapshots on baseline_date (2026-09-30), then inject Story E
            if snap_d == baseline_date:
                ym_key = (aid, snap_d.year, snap_d.month)
                rep_nna = monthly_nna_acc.get(ym_key, Decimal("0.00"))
                rep_in = monthly_inflow_acc.get(ym_key, Decimal("0.00"))
                rep_out = monthly_outflow_acc.get(ym_key, Decimal("0.00"))
                rep_fee = monthly_fee_acc.get(ym_key, Decimal("0.00"))
                rec_hash = hashlib.sha256(f"{aid}:{snap_d.isoformat()}:{total_aum}".encode()).hexdigest()
                reported_rows.append((
                    det_uuid(seed, "rep", f"{aid}:{snap_d.isoformat()}"),
                    "MGMT_REPORT_FEED_Q3",
                    aid,
                    meta["advisor_id"],
                    meta["segment_id"],
                    snap_d,
                    total_aum,
                    rep_in,
                    rep_out,
                    rep_nna,
                    Decimal("0.00"),
                    rep_fee,
                    rec_hash,
                    False,
                    run_id,
                ))

        prev_snap_date = snap_d

    # 6. Inject Story E Controlled Discrepancies into reported_asset_snapshots
    # E1: Duplicate financial record in reporting feed (index 10)
    dup_target = reported_rows[10]
    reported_rows.append((
        det_uuid(seed, "rep_dup", 1),
        dup_target[1], dup_target[2], dup_target[3], dup_target[4], dup_target[5],
        dup_target[6], dup_target[7], dup_target[8], dup_target[9], dup_target[10],
        dup_target[11], dup_target[12], True, run_id,
    ))

    # E2: Missing transaction in reporting aggregate (index 20: omit $250,000 from reported_nna and reported_aum)
    m_row = list(reported_rows[20])
    m_row[6] = m_row[6] - Decimal("250000.00")
    m_row[9] = m_row[9] - Decimal("250000.00")
    m_row[13] = True
    reported_rows[20] = tuple(m_row)

    # E4: Incorrect advisor or segment classification in reporting feed (indices 30, 31, 32)
    wrong_adv = advisors_meta[2]["advisor_id"]
    wrong_seg = segment_ids["WPW"]
    for idx_e4 in (30, 31, 32):
        c_row = list(reported_rows[idx_e4])
        c_row[3] = wrong_adv
        c_row[4] = wrong_seg
        c_row[13] = True
        reported_rows[idx_e4] = tuple(c_row)

    manifest = {
        "profile": profile_name,
        "seed": seed,
        "baseline_date": baseline_date.isoformat(),
        "stories": {
            "STORY_A": {
                "description": "Concentrated Q3 2026 external outflows on ADV-001",
                "advisor_code": "ADV-001",
                "affected_accounts": [a["account_number"] for a in story_a_accounts],
            },
            "STORY_B": {
                "description": "Rate-driven sweep-to-external cash outflows",
                "affected_accounts_count": len(story_b_accounts[:12]),
            },
            "STORY_C": {
                "description": "Market-driven AUM growth in Self-Directed Investing (SDI)",
                "segment_code": "SDI",
            },
            "STORY_D": {
                "description": "High-growth advisor ADV-002 via diversified new client inflows",
                "advisor_code": "ADV-002",
            },
            "STORY_E": [
                {
                    "scenario_id": "E1_DUPLICATE_FEED_RECORD",
                    "affected_account": str(dup_target[2]),
                    "issue_type": "DUPLICATE_RECORD",
                    "affected_period": "2026-09-30",
                    "detection_method": "GROUP BY feed_source, account_id, as_of_date, record_hash HAVING COUNT(*) > 1",
                    "expected_financial_impact_usd": str(dup_target[6]),
                },
                {
                    "scenario_id": "E2_MISSING_TX_IN_REPORTING",
                    "affected_account": str(reported_rows[20][2]),
                    "issue_type": "MISSING_TRANSACTION_AGGREGATE",
                    "affected_period": "2026-09-30",
                    "detection_method": "Compare marts.monthly_asset_snapshots vs raw.reported_asset_snapshots",
                    "expected_financial_impact_usd": "-250000.00",
                },
                {
                    "scenario_id": "E3_LATE_POSTED_TRANSFER",
                    "affected_account": late_posted_transfer_ref["source_account"] if late_posted_transfer_ref else None,
                    "issue_type": "LATE_POSTED_TRANSFER",
                    "affected_period": "2026-Q3",
                    "detection_method": "DATE_TRUNC('month', effective_date) <> DATE_TRUNC('month', posted_date)",
                    "expected_financial_impact_usd": "150000.00",
                },
                {
                    "scenario_id": "E4_INCORRECT_CLASSIFICATION",
                    "affected_accounts": [str(reported_rows[i][2]) for i in (30, 31, 32)],
                    "issue_type": "CLASSIFICATION_MISMATCH",
                    "affected_period": "2026-09-30",
                    "detection_method": "Compare raw.reported_asset_snapshots advisor_id/segment_id vs raw.accounts",
                    "expected_financial_impact_usd": "0.00",
                },
            ],
        },
    }

    row_counts = {
        "business_segments": len(segment_rows),
        "asset_classes": len(asset_class_rows),
        "securities": len(security_rows),
        "calendar": len(calendar_rows),
        "reporting_periods": len(reporting_period_rows),
        "advisors": len(advisor_rows),
        "client_households": len(household_rows),
        "clients": len(client_rows),
        "accounts": len(account_rows),
        "security_prices": len(security_price_rows),
        "transaction_events": len(tx_rows),
        "transaction_legs": len(leg_rows),
        "account_cash_balances": len(cash_bal_rows),
        "position_snapshots": len(pos_snap_rows),
        "account_valuations": len(acct_val_rows),
        "reported_asset_snapshots": len(reported_rows),
        "fee_events": len(fee_rows),
        "income_events": len(income_rows),
    }

    # 7. Idempotent PostgreSQL Load
    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                TRUNCATE TABLE
                    raw.audit_events,
                    raw.reconciliation_issues,
                    raw.validation_results,
                    raw.metric_definitions,
                    raw.income_events,
                    raw.fee_events,
                    raw.reported_asset_snapshots,
                    raw.account_valuations,
                    raw.position_snapshots,
                    raw.account_cash_balances,
                    raw.transaction_legs,
                    raw.transaction_events,
                    raw.security_prices,
                    raw.account_classification_history,
                    raw.advisor_assignment_history,
                    raw.accounts,
                    raw.clients,
                    raw.client_households,
                    raw.advisors,
                    raw.securities,
                    raw.asset_classes,
                    raw.business_segments,
                    raw.reporting_periods,
                    raw.calendar,
                    raw.ingestion_runs
                CASCADE;
                """
            )

            cur.execute(
                """
                INSERT INTO raw.ingestion_runs
                    (run_id, profile, seed, baseline_date, started_at, completed_at, status, row_counts_json, manifest_json)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    run_id, profile_name, seed, baseline_date, now_utc, now_utc,
                    "COMPLETED", json.dumps(row_counts), json.dumps(manifest),
                ),
            )

            copy_rows(cur, "raw.business_segments", ["segment_id", "segment_code", "segment_name", "description"], segment_rows)
            copy_rows(cur, "raw.asset_classes", ["asset_class_id", "asset_class_code", "asset_class_name", "is_cash"], asset_class_rows)
            copy_rows(cur, "raw.securities", ["security_id", "ticker", "security_name", "asset_class_id", "is_cash_equivalent", "base_price_usd", "annual_drift", "annual_vol"], security_rows)
            copy_rows(cur, "raw.calendar", ["calendar_date", "year", "quarter", "month", "day_of_week", "is_business_day", "is_month_end", "is_quarter_end", "is_90d_window"], calendar_rows)
            copy_rows(cur, "raw.reporting_periods", ["period_id", "period_code", "period_type", "start_date", "end_date", "is_closed"], reporting_period_rows)
            copy_rows(cur, "raw.advisors", ["advisor_id", "advisor_code", "full_name", "segment_id", "region", "hire_date", "status", "created_at"], advisor_rows)
            copy_rows(cur, "raw.client_households", ["household_id", "household_code", "household_name", "primary_segment_id", "created_at"], household_rows)
            copy_rows(cur, "raw.clients", ["client_id", "client_code", "household_id", "full_name", "client_tier", "risk_profile", "onboarding_date", "status", "created_at"], client_rows)
            copy_rows(cur, "raw.accounts", ["account_id", "account_number", "client_id", "household_id", "segment_id", "advisor_id", "account_type", "opened_date", "closed_date", "currency", "status", "created_at"], account_rows)
            copy_rows(cur, "raw.advisor_assignment_history", ["assignment_id", "client_id", "account_id", "advisor_id", "effective_from", "effective_to", "is_current", "assignment_reason", "created_at"], adv_assign_rows)
            copy_rows(cur, "raw.account_classification_history", ["classification_id", "account_id", "segment_id", "advisor_id", "account_type", "effective_from", "effective_to", "is_current", "created_at"], acct_class_rows)
            copy_rows(cur, "raw.security_prices", ["price_id", "security_id", "price_date", "close_price_usd", "daily_return"], security_price_rows)
            copy_rows(cur, "raw.transaction_events", [
                "event_id", "external_ref", "account_id", "advisor_id", "segment_id",
                "event_type", "effective_date", "posted_date", "trade_timestamp",
                "security_id", "quantity", "unit_price", "gross_amount", "fee_amount", "net_amount",
                "currency", "nna_eligible", "external_flow_eligible", "is_internal_transfer",
                "counterparty_account_id", "transfer_group_id", "description", "ingestion_run_id", "created_at",
            ], tx_rows)
            copy_rows(cur, "raw.transaction_legs", [
                "leg_id", "event_id", "transfer_group_id", "account_id", "leg_side",
                "asset_or_cash", "security_id", "quantity_delta", "amount_usd", "effective_date", "posted_date",
            ], leg_rows)
            copy_rows(cur, "raw.account_cash_balances", ["balance_id", "account_id", "as_of_date", "cash_balance_usd", "sweep_balance_usd"], cash_bal_rows)
            copy_rows(cur, "raw.position_snapshots", ["snapshot_id", "account_id", "security_id", "as_of_date", "quantity", "market_price_usd", "market_value_usd", "cost_basis_usd"], pos_snap_rows)
            copy_rows(cur, "raw.account_valuations", ["valuation_id", "account_id", "as_of_date", "period_granularity", "cash_value_usd", "securities_value_usd", "total_aum_usd", "advisor_id", "segment_id"], acct_val_rows)
            copy_rows(cur, "raw.reported_asset_snapshots", [
                "reported_id", "feed_source", "account_id", "advisor_id", "segment_id", "as_of_date",
                "reported_aum_usd", "reported_inflows_usd", "reported_outflows_usd",
                "reported_nna_usd", "reported_market_change_usd", "reported_fees_usd",
                "record_hash", "is_corrupted_feed", "ingestion_run_id",
            ], reported_rows)
            copy_rows(cur, "raw.fee_events", ["fee_event_id", "event_id", "account_id", "advisor_id", "fee_type", "effective_date", "posted_date", "fee_amount_usd"], fee_rows)
            copy_rows(cur, "raw.income_events", ["income_event_id", "event_id", "account_id", "security_id", "income_type", "effective_date", "posted_date", "amount_usd", "is_reinvested"], income_rows)

            # Populate metric_definitions
            metrics = [
                (det_uuid(seed, "metric", "FIRM_STYLE_NNA"), "FIRM_STYLE_NNA", "Firm-Style Net New Assets", "External Inflows + Credited Income + In-Kind Acquisitions - External Outflows", "marts.monthly_asset_snapshots.firm_style_nna_usd", "Wealth Analytics", "v1.0.0"),
                (det_uuid(seed, "metric", "EXTERNAL_NET_FLOWS"), "EXTERNAL_NET_FLOWS", "External Net Flows", "External Inflows - External Outflows", "marts.monthly_asset_snapshots.external_net_flows_usd", "Wealth Analytics", "v1.0.0"),
                (det_uuid(seed, "metric", "MARKET_APPRECIATION"), "MARKET_APPRECIATION", "Market Appreciation", "Ending AUM - Beginning AUM - Firm-Style NNA - Internal Transfer Net + Fees", "marts.monthly_asset_snapshots.market_appreciation_usd", "Quantitative Attribution", "v1.0.0"),
            ]
            copy_rows(cur, "raw.metric_definitions", ["metric_id", "metric_code", "metric_name", "formula_text", "sql_source", "owner", "calculation_version"], metrics)

            # Log audit event
            cur.execute(
                """
                INSERT INTO raw.audit_events (audit_id, run_id, actor, action, entity_type, entity_id, payload_json, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (det_uuid(seed, "audit", 1), run_id, "data.generator", "SEED_COMPLETED", "ingestion_run", str(run_id), json.dumps(row_counts), now_utc),
            )

        conn.commit()

    manifest_path = Path("data/seeds") / f"seed_manifest_{profile_name}_{seed}.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2))

    return GenerationSummary(
        run_id=run_id,
        profile=profile_name,
        seed=seed,
        baseline_date=baseline_date,
        row_counts=row_counts,
        manifest=manifest,
        duration_seconds=round(time.perf_counter() - t0, 2),
    )
