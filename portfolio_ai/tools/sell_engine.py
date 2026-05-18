"""
Sell engine: translates EvaluationResults into SellOrders and submits them.
"""
from __future__ import annotations

from portfolio_ai.brokers.base import BaseBroker
from portfolio_ai.models.portfolio import EvaluationResult, OrderType, Position, SellOrder, SignalStrength


SELL_SIGNALS = {SignalStrength.SELL, SignalStrength.STRONG_SELL}


def build_sell_order(
    position: Position,
    result: EvaluationResult,
    dry_run: bool = True,
    use_limit: bool = False,
    limit_pct_below: float = 0.005,  # 0.5% below current price for limit orders
) -> SellOrder | None:
    """Return a SellOrder if the evaluation recommends selling, else None."""
    if result.signal not in SELL_SIGNALS:
        return None

    order_type = OrderType.MARKET
    limit_price = None

    if use_limit:
        order_type = OrderType.LIMIT
        limit_price = round(position.current_price * (1 - limit_pct_below), 4)

    return SellOrder(
        ticker=position.ticker,
        quantity=position.quantity,
        order_type=order_type,
        limit_price=limit_price,
        stop_price=result.stop_loss,
        reason=f"{result.signal.value} (confidence={result.confidence:.0%}): {result.analyst_summary[:120]}",
        dry_run=dry_run,
    )


async def execute_sell_orders(
    orders: list[SellOrder],
    broker: BaseBroker,
) -> list[SellOrder]:
    """Submit all orders through the broker (respects dry_run flag on each order)."""
    results: list[SellOrder] = []
    for order in orders:
        submitted = await broker.submit_sell_order(order)
        results.append(submitted)
    return results
