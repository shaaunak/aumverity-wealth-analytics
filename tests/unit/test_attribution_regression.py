from decimal import Decimal

from app.services.attribution import PositionState, TxRecord, compute_account_bridge

ZERO = Decimal("0.00")


def test_01_security_purchase_no_nna_and_commission_explicit():
    res = compute_account_bridge(
        opening_cash_usd=Decimal("10000.00"),
        opening_positions={},
        closing_cash_usd=Decimal("4995.05"),
        closing_positions={"SEC1": PositionState("SEC1", Decimal("50"), Decimal("100.00"))},
        closing_prices_usd={"SEC1": Decimal("100.00")},
        transactions=[
            TxRecord(
                event_type="SECURITY_PURCHASE",
                gross_amount=Decimal("5000.00"),
                fee_amount=Decimal("4.95"),
                net_amount=Decimal("-5004.95"),
                security_id="SEC1",
                quantity_delta=Decimal("50"),
                unit_price_usd=Decimal("100.00"),
            )
        ],
    )
    assert res.firm_style_nna_usd == ZERO
    assert res.external_net_flows_usd == ZERO
    assert res.fees_and_commissions_usd == Decimal("4.95")
    assert res.unexplained_residual_usd == ZERO


def test_02_security_sale_conserves_value():
    res = compute_account_bridge(
        opening_cash_usd=Decimal("1000.00"),
        opening_positions={"SEC1": PositionState("SEC1", Decimal("20"), Decimal("100.00"))},
        closing_cash_usd=Decimal("3000.00"),
        closing_positions={},
        closing_prices_usd={"SEC1": Decimal("100.00")},
        transactions=[
            TxRecord(
                event_type="SECURITY_SALE",
                gross_amount=Decimal("2000.00"),
                net_amount=Decimal("2000.00"),
                security_id="SEC1",
                quantity_delta=Decimal("-20"),
                unit_price_usd=Decimal("100.00"),
            )
        ],
    )
    assert res.firm_style_nna_usd == ZERO
    assert res.actual_closing_assets_usd == Decimal("3000.00")
    assert res.unexplained_residual_usd == ZERO


def test_03_price_increase_attributed_to_market():
    res = compute_account_bridge(
        opening_cash_usd=Decimal("500.00"),
        opening_positions={"SEC1": PositionState("SEC1", Decimal("10"), Decimal("100.00"))},
        closing_cash_usd=Decimal("500.00"),
        closing_positions={"SEC1": PositionState("SEC1", Decimal("10"), Decimal("115.00"))},
        closing_prices_usd={"SEC1": Decimal("115.00")},
        transactions=[],
    )
    assert res.price_driven_market_movement_usd == Decimal("150.00")
    assert res.firm_style_nna_usd == ZERO
    assert res.unexplained_residual_usd == ZERO


def test_04_price_decrease_handled_negatively():
    res = compute_account_bridge(
        opening_cash_usd=Decimal("500.00"),
        opening_positions={"SEC1": PositionState("SEC1", Decimal("10"), Decimal("100.00"))},
        closing_cash_usd=Decimal("500.00"),
        closing_positions={"SEC1": PositionState("SEC1", Decimal("10"), Decimal("82.50"))},
        closing_prices_usd={"SEC1": Decimal("82.50")},
        transactions=[],
    )
    assert res.price_driven_market_movement_usd == Decimal("-175.00")
    assert res.actual_closing_assets_usd == Decimal("1325.00")
    assert res.unexplained_residual_usd == ZERO


def test_05_dividend_payment_and_reinvestment_no_double_count():
    res = compute_account_bridge(
        opening_cash_usd=Decimal("0.00"),
        opening_positions={"SEC1": PositionState("SEC1", Decimal("100"), Decimal("50.00"))},
        closing_cash_usd=Decimal("0.00"),
        closing_positions={"SEC1": PositionState("SEC1", Decimal("104"), Decimal("50.00"))},
        closing_prices_usd={"SEC1": Decimal("50.00")},
        transactions=[
            TxRecord(
                event_type="DIVIDEND_CREDITED",
                gross_amount=Decimal("200.00"),
                net_amount=Decimal("200.00"),
                security_id="SEC1",
            ),
            TxRecord(
                event_type="DIVIDEND_REINVESTMENT",
                gross_amount=Decimal("200.00"),
                net_amount=Decimal("0.00"),
                security_id="SEC1",
                quantity_delta=Decimal("4"),
                unit_price_usd=Decimal("50.00"),
            ),
        ],
    )
    assert res.external_net_flows_usd == ZERO
    assert res.firm_style_nna_usd == Decimal("200.00")
    assert res.unexplained_residual_usd == ZERO


def test_06_stock_split_preserves_value_zero_market_impact():
    res = compute_account_bridge(
        opening_cash_usd=Decimal("100.00"),
        opening_positions={"SEC1": PositionState("SEC1", Decimal("10"), Decimal("200.00"))},
        closing_cash_usd=Decimal("100.00"),
        closing_positions={"SEC1": PositionState("SEC1", Decimal("20"), Decimal("100.00"))},
        closing_prices_usd={"SEC1": Decimal("100.00")},
        transactions=[
            TxRecord(
                event_type="CORPORATE_ACTION",
                gross_amount=ZERO,
                net_amount=ZERO,
                security_id="SEC1",
                split_ratio=Decimal("2"),
            )
        ],
    )
    assert res.price_driven_market_movement_usd == ZERO
    assert res.firm_style_nna_usd == ZERO
    assert res.unexplained_residual_usd == ZERO


def test_07_fee_deduction_reduces_aum_explicitly():
    res = compute_account_bridge(
        opening_cash_usd=Decimal("5000.00"),
        opening_positions={},
        closing_cash_usd=Decimal("4875.00"),
        closing_positions={},
        closing_prices_usd={},
        transactions=[
            TxRecord(
                event_type="MANAGEMENT_FEE",
                gross_amount=Decimal("125.00"),
                fee_amount=Decimal("125.00"),
                net_amount=Decimal("-125.00"),
            )
        ],
    )
    assert res.fees_and_commissions_usd == Decimal("125.00")
    assert res.firm_style_nna_usd == ZERO
    assert res.unexplained_residual_usd == ZERO


def test_08_cash_deposit_creates_external_flow_and_nna():
    res = compute_account_bridge(
        opening_cash_usd=Decimal("1000.00"),
        opening_positions={},
        closing_cash_usd=Decimal("6000.00"),
        closing_positions={},
        closing_prices_usd={},
        transactions=[
            TxRecord(
                event_type="EXTERNAL_DEPOSIT",
                gross_amount=Decimal("5000.00"),
                net_amount=Decimal("5000.00"),
            )
        ],
    )
    assert res.external_net_flows_usd == Decimal("5000.00")
    assert res.firm_style_nna_usd == Decimal("5000.00")
    assert res.unexplained_residual_usd == ZERO


def test_09_in_kind_external_transfer_creates_nna_and_zero_residual():
    res = compute_account_bridge(
        opening_cash_usd=Decimal("0.00"),
        opening_positions={},
        closing_cash_usd=Decimal("0.00"),
        closing_positions={"SEC1": PositionState("SEC1", Decimal("10"), Decimal("150.00"))},
        closing_prices_usd={"SEC1": Decimal("150.00")},
        transactions=[
            TxRecord(
                event_type="IN_KIND_ACQUISITION",
                gross_amount=Decimal("1500.00"),
                net_amount=Decimal("1500.00"),
                security_id="SEC1",
                quantity_delta=Decimal("10"),
                unit_price_usd=Decimal("150.00"),
            )
        ],
    )
    assert res.external_net_flows_usd == Decimal("1500.00")
    assert res.firm_style_nna_usd == Decimal("1500.00")
    assert res.unexplained_residual_usd == ZERO
