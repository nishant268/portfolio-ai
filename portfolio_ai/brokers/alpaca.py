from __future__ import annotations

import os
from datetime import datetime

from portfolio_ai.brokers.base import BaseBroker
from portfolio_ai.models.portfolio import AssetClass, OrderType, Portfolio, Position, SellOrder


class AlpacaBroker(BaseBroker):
    """Alpaca Markets broker — supports US stocks and crypto."""

    def __init__(self, api_key: str | None = None, secret_key: str | None = None, paper: bool = True) -> None:
        self._api_key = api_key or os.environ["ALPACA_API_KEY"]
        self._secret_key = secret_key or os.environ["ALPACA_SECRET_KEY"]
        self._paper = paper
        self._base_url = (
            "https://paper-api.alpaca.markets" if paper else "https://api.alpaca.markets"
        )
        self._client = self._build_client()

    def _build_client(self):  # type: ignore[no-untyped-def]
        try:
            from alpaca.trading.client import TradingClient
            return TradingClient(self._api_key, self._secret_key, paper=self._paper)
        except ImportError:
            raise RuntimeError("Install alpaca-py: pip install alpaca-py")

    async def get_portfolio(self) -> Portfolio:
        from alpaca.trading.requests import GetAssetsRequest

        account = self._client.get_account()
        raw_positions = self._client.get_all_positions()

        positions: list[Position] = []
        for pos in raw_positions:
            positions.append(
                Position(
                    ticker=pos.symbol,
                    asset_class=AssetClass.CRYPTO if pos.asset_class == "crypto" else AssetClass.STOCK,
                    quantity=float(pos.qty),
                    avg_cost=float(pos.avg_entry_price),
                    current_price=float(pos.current_price),
                    broker="alpaca",
                )
            )

        return Portfolio(
            positions=positions,
            cash=float(account.cash),
            broker="alpaca",
            fetched_at=datetime.utcnow(),
        )

    async def get_current_price(self, ticker: str) -> float:
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import StockLatestTradeRequest

        data_client = StockHistoricalDataClient(self._api_key, self._secret_key)
        request = StockLatestTradeRequest(symbol_or_symbols=ticker)
        trade = data_client.get_stock_latest_trade(request)
        return float(trade[ticker].price)

    async def submit_sell_order(self, order: SellOrder) -> SellOrder:
        from alpaca.trading.enums import OrderSide, OrderType as AOrderType, TimeInForce
        from alpaca.trading.requests import LimitOrderRequest, MarketOrderRequest, StopLimitOrderRequest

        if order.dry_run:
            order.status = "dry_run_skipped"
            order.submitted_at = datetime.utcnow()
            return order

        if order.order_type == OrderType.MARKET:
            req = MarketOrderRequest(
                symbol=order.ticker,
                qty=order.quantity,
                side=OrderSide.SELL,
                time_in_force=TimeInForce.DAY,
            )
        elif order.order_type == OrderType.LIMIT and order.limit_price:
            req = LimitOrderRequest(
                symbol=order.ticker,
                qty=order.quantity,
                side=OrderSide.SELL,
                time_in_force=TimeInForce.DAY,
                limit_price=order.limit_price,
            )
        else:
            raise ValueError(f"Unsupported order type: {order.order_type}")

        result = self._client.submit_order(req)
        order.broker_order_id = str(result.id)
        order.status = str(result.status)
        order.submitted_at = datetime.utcnow()
        return order
