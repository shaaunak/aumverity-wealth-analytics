from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

ZERO = Decimal("0.00")


def q2(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class PositionState:
    security_id: str
    quantity: Decimal
    price_usd: Decimal


@dataclass(frozen=True)
class TxRecord:
    event_type: str
    gross_amount: Decimal
    fee_amount: Decimal = ZERO
    net_amount: Decimal = ZERO
    security_id: str | None = None
    quantity_delta: Decimal | None = None
    unit_price_usd: Decimal | None = None
    split_ratio: Decimal | None = None


@dataclass(frozen=True)
class AccountBridgeResult:
    opening_assets_usd: Decimal
    external_net_flows_usd: Decimal
    firm_style_nna_usd: Decimal
    price_driven_market_movement_usd: Decimal
    fees_and_commissions_usd: Decimal
    explicit_other_adjustments_usd: Decimal
    expected_closing_assets_usd: Decimal
    actual_closing_assets_usd: Decimal
    unexplained_residual_usd: Decimal


def compute_account_bridge(
    opening_cash_usd: Decimal,
    opening_positions: dict[str, PositionState],
    closing_cash_usd: Decimal,
    closing_positions: dict[str, PositionState],
    closing_prices_usd: dict[str, Decimal],
    transactions: list[TxRecord],
) -> AccountBridgeResult:
    """
    Deterministic Decimal asset-movement bridge using End-of-Day (EOD) snapshot convention.
    Market movement is computed independently from position holdings and prices—never as a residual plug.
    """
    opening_sec_val = sum(
        (q2(p.quantity * p.price_usd) for p in opening_positions.values()), ZERO
    )
    opening_assets = q2(opening_cash_usd + opening_sec_val)

    closing_sec_val = sum(
        (q2(p.quantity * p.price_usd) for p in closing_positions.values()), ZERO
    )
    actual_closing = q2(closing_cash_usd + closing_sec_val)

    # 1. Price-driven market movement on opening positions (adjusted for stock splits)
    split_multipliers: dict[str, Decimal] = {}
    for tx in transactions:
        if tx.event_type == "CORPORATE_ACTION" and tx.security_id and tx.split_ratio:
            split_multipliers[tx.security_id] = (
                split_multipliers.get(tx.security_id, Decimal("1")) * tx.split_ratio
            )

    market_movement = ZERO
    for sec_id, pos in opening_positions.items():
        ratio = split_multipliers.get(sec_id, Decimal("1"))
        effective_qty = pos.quantity * ratio
        # Pre-split price adjusted to post-split basis so split itself produces 0.00 market movement
        adj_open_price = pos.price_usd / ratio
        close_price = closing_prices_usd.get(sec_id, adj_open_price)
        market_movement += q2(effective_qty * (close_price - adj_open_price))

    # 2. Intra-period trade price movement (from execution price to period-end price)
    for tx in transactions:
        if (
            tx.event_type
            in ("SECURITY_PURCHASE", "SECURITY_SALE", "DIVIDEND_REINVESTMENT", "IN_KIND_ACQUISITION")
            and tx.security_id
            and tx.quantity_delta is not None
            and tx.unit_price_usd is not None
        ):
            close_price = closing_prices_usd.get(tx.security_id, tx.unit_price_usd)
            market_movement += q2(tx.quantity_delta * (close_price - tx.unit_price_usd))

    # 3. Flow, NNA, Fee, and Internal Transfer classification
    external_net_flows = ZERO
    firm_style_nna = ZERO
    fees_and_commissions = ZERO
    other_adjustments = ZERO

    for tx in transactions:
        if tx.event_type in ("EXTERNAL_DEPOSIT", "EXTERNAL_TRANSFER_IN", "IN_KIND_ACQUISITION"):
            external_net_flows += tx.net_amount
            firm_style_nna += tx.net_amount
        elif tx.event_type in ("EXTERNAL_WITHDRAWAL", "EXTERNAL_TRANSFER_OUT"):
            external_net_flows += tx.net_amount
            firm_style_nna += tx.net_amount
        elif tx.event_type in ("INTEREST_CREDITED", "DIVIDEND_CREDITED"):
            firm_style_nna += tx.net_amount
        elif tx.event_type == "DIVIDEND_REINVESTMENT":
            # Reinvestment is an internal cash-to-security conversion; never double-counts NNA
            pass
        elif tx.event_type in ("SECURITY_PURCHASE", "SECURITY_SALE"):
            fees_and_commissions += tx.fee_amount
        elif tx.event_type in ("MANAGEMENT_FEE", "COMMISSION"):
            fees_and_commissions += abs(tx.net_amount) if tx.fee_amount == ZERO else tx.fee_amount
        elif tx.event_type == "INTERNAL_ACCOUNT_TRANSFER":
            other_adjustments += tx.net_amount

    expected_closing = q2(
        opening_assets
        + firm_style_nna
        + market_movement
        - fees_and_commissions
        + other_adjustments
    )
    residual = q2(actual_closing - expected_closing)

    return AccountBridgeResult(
        opening_assets_usd=opening_assets,
        external_net_flows_usd=q2(external_net_flows),
        firm_style_nna_usd=q2(firm_style_nna),
        price_driven_market_movement_usd=q2(market_movement),
        fees_and_commissions_usd=q2(fees_and_commissions),
        explicit_other_adjustments_usd=q2(other_adjustments),
        expected_closing_assets_usd=expected_closing,
        actual_closing_assets_usd=actual_closing,
        unexplained_residual_usd=residual,
    )
