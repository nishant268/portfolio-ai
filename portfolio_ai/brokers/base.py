from __future__ import annotations

from abc import ABC, abstractmethod

from portfolio_ai.models.portfolio import Portfolio, SellOrder


class BaseBroker(ABC):
    """Abstract broker interface — implement for Alpaca, Zerodha, IBKR, etc."""

    @abstractmethod
    async def get_portfolio(self) -> Portfolio:
        """Fetch all open positions and cash balance."""
        ...

    @abstractmethod
    async def submit_sell_order(self, order: SellOrder) -> SellOrder:
        """Submit a sell order. Returns updated order with broker_order_id and status."""
        ...

    @abstractmethod
    async def get_current_price(self, ticker: str) -> float:
        """Fetch latest market price for a ticker."""
        ...
