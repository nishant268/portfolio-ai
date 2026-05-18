from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, computed_field


class AssetClass(str, Enum):
    STOCK = "stock"
    CRYPTO = "crypto"
    ETF = "etf"
    OPTION = "option"


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class SignalStrength(str, Enum):
    STRONG_SELL = "STRONG_SELL"
    SELL = "SELL"
    HOLD = "HOLD"
    BUY = "BUY"
    STRONG_BUY = "STRONG_BUY"


class Position(BaseModel):
    ticker: str
    asset_class: AssetClass = AssetClass.STOCK
    quantity: float
    avg_cost: float
    current_price: float = 0.0
    broker: str = "alpaca"

    @computed_field
    @property
    def market_value(self) -> float:
        return self.quantity * self.current_price

    @computed_field
    @property
    def cost_basis(self) -> float:
        return self.quantity * self.avg_cost

    @computed_field
    @property
    def unrealized_pnl(self) -> float:
        return self.market_value - self.cost_basis

    @computed_field
    @property
    def unrealized_pnl_pct(self) -> float:
        if self.cost_basis == 0:
            return 0.0
        return (self.unrealized_pnl / self.cost_basis) * 100


class Portfolio(BaseModel):
    positions: list[Position] = Field(default_factory=list)
    cash: float = 0.0
    broker: str = "alpaca"
    fetched_at: datetime = Field(default_factory=datetime.utcnow)

    @computed_field
    @property
    def total_market_value(self) -> float:
        return sum(p.market_value for p in self.positions)

    @computed_field
    @property
    def total_cost_basis(self) -> float:
        return sum(p.cost_basis for p in self.positions)

    @computed_field
    @property
    def total_unrealized_pnl(self) -> float:
        return self.total_market_value - self.total_cost_basis

    @computed_field
    @property
    def total_value(self) -> float:
        return self.total_market_value + self.cash

    @computed_field
    @property
    def total_pnl_pct(self) -> float:
        if self.total_cost_basis == 0:
            return 0.0
        return (self.total_unrealized_pnl / self.total_cost_basis) * 100


class EvaluationResult(BaseModel):
    ticker: str
    signal: SignalStrength
    confidence: float = Field(ge=0.0, le=1.0)
    analyst_summary: str
    risk_score: float = Field(ge=0.0, le=10.0)
    suggested_action: str
    target_price: Optional[float] = None
    stop_loss: Optional[float] = None
    reasoning: dict[str, str] = Field(default_factory=dict)


class SellOrder(BaseModel):
    ticker: str
    quantity: float
    order_type: OrderType = OrderType.MARKET
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    reason: str = ""
    dry_run: bool = True
    broker_order_id: Optional[str] = None
    submitted_at: Optional[datetime] = None
    status: str = "pending"
