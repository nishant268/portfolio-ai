from __future__ import annotations

import os
from datetime import datetime

from portfolio_ai.brokers.base import BaseBroker
from portfolio_ai.models.portfolio import AssetClass, OrderType, Portfolio, Position, SellOrder


class ZerodhaBroker(BaseBroker):
    """Zerodha Kite Connect broker — Indian markets (NSE/BSE)."""

    def __init__(self, api_key: str | None = None, access_token: str | None = None) -> None:
        self._api_key = api_key or os.environ["ZERODHA_API_KEY"]
        self._access_token = access_token or os.environ["ZERODHA_ACCESS_TOKEN"]
        self._kite = self._build_client()

    def _build_client(self):  # type: ignore[no-untyped-def]
        try:
            from kiteconnect import KiteConnect
            kite = KiteConnect(api_key=self._api_key)
            kite.set_access_token(self._access_token)
            return kite
        except ImportError:
            raise RuntimeError("Install kiteconnect: pip install kiteconnect")

    async def get_portfolio(self) -> Portfolio:
        holdings = self._kite.holdings()
        positions_data = self._kite.positions()

        positions: list[Position] = []

        for h in holdings:
            if h["quantity"] > 0:
                positions.append(
                    Position(
                        ticker=h["tradingsymbol"],
                        asset_class=AssetClass.STOCK,
                        quantity=float(h["quantity"]),
                        avg_cost=float(h["average_price"]),
                        current_price=float(h["last_price"]),
                        broker="zerodha",
                    )
                )

        margins = self._kite.margins()
        cash = float(margins.get("equity", {}).get("available", {}).get("cash", 0.0))

        return Portfolio(
            positions=positions,
            cash=cash,
            broker="zerodha",
            fetched_at=datetime.utcnow(),
        )

    async def get_current_price(self, ticker: str) -> float:
        quote = self._kite.quote([f"NSE:{ticker}"])
        return float(quote[f"NSE:{ticker}"]["last_price"])

    async def submit_sell_order(self, order: SellOrder) -> SellOrder:
        from kiteconnect import KiteConnect

        if order.dry_run:
            order.status = "dry_run_skipped"
            order.submitted_at = datetime.utcnow()
            return order

        variety = KiteConnect.VARIETY_REGULAR
        order_type = KiteConnect.ORDER_TYPE_MARKET
        if order.order_type == OrderType.LIMIT:
            order_type = KiteConnect.ORDER_TYPE_LIMIT
        elif order.order_type == OrderType.STOP:
            order_type = KiteConnect.ORDER_TYPE_SL

        order_id = self._kite.place_order(
            variety=variety,
            exchange=KiteConnect.EXCHANGE_NSE,
            tradingsymbol=order.ticker,
            transaction_type=KiteConnect.TRANSACTION_TYPE_SELL,
            quantity=int(order.quantity),
            order_type=order_type,
            product=KiteConnect.PRODUCT_CNC,
            price=order.limit_price,
            trigger_price=order.stop_price,
        )

        order.broker_order_id = str(order_id)
        order.status = "submitted"
        order.submitted_at = datetime.utcnow()
        return order
