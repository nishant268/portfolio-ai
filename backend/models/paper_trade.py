from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path

from sqlmodel import Field, Session, SQLModel, create_engine, select

import os as _os
_DATA_DIR = Path(_os.environ.get("DATA_DIR", Path(__file__).parent.parent.parent))
_DATA_DIR.mkdir(parents=True, exist_ok=True)
_DB = _DATA_DIR / "paper_trade.db"
engine = create_engine(f"sqlite:///{_DB}", connect_args={"check_same_thread": False})


class PaperPortfolio(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    name: str = "AI Paper Portfolio"
    mode: str = "investor"          # investor | trader
    initial_capital: float = 20_000.0      # ₹20,000 starting paper capital
    cash: float = 20_000.0
    is_active: bool = True
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    started_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    target_days: int = 15


class PaperPosition(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    portfolio_id: str = Field(index=True)
    ticker: str
    quantity: float
    avg_entry_price: float
    entry_date: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    stop_loss: float = 0.0
    take_profit: float = 0.0
    direction: str = "long"         # long | short


class PaperTrade(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    portfolio_id: str = Field(index=True)
    ticker: str
    action: str                    # BUY | SELL | SHORT | COVER
    quantity: float
    price: float
    trade_value: float
    pnl: float = 0.0               # realised P&L (on sell)
    signal: str = ""               # STRONG_BUY etc.
    reasoning: str = ""            # full AI reasoning
    why_summary: str = ""          # one-line "why" — shown inline in trade history
    technicals_snapshot: str = "{}"# JSON of RSI/MACD etc at trade time
    executed_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    session_market_view: str = ""  # AI's overall market view for this session


class PaperDailySnapshot(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    portfolio_id: str = Field(index=True)
    date: str                      # YYYY-MM-DD
    portfolio_value: float
    cash: float
    positions_value: float
    daily_pnl: float
    daily_pnl_pct: float
    total_pnl: float
    total_pnl_pct: float
    nifty_value: float = 0.0       # benchmark snapshot
    recorded_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class PaperTradeAnalysis(SQLModel, table=True):
    """Detailed bull/bear/researcher debate for each executed trade. One Claude call per trade."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    trade_id: str = Field(index=True, unique=True)
    portfolio_id: str = Field(index=True)
    ticker: str
    action: str
    # Bull analyst
    bull_thesis: str = ""
    bull_catalysts: str = "[]"      # JSON list
    bull_target: float = 0.0
    bull_confidence: str = "medium"
    # Bear analyst
    bear_thesis: str = ""
    bear_risks: str = "[]"          # JSON list
    bear_stop: float = 0.0
    bear_confidence: str = "medium"
    # Researcher synthesis
    researcher_verdict: str = ""
    researcher_reasoning: str = ""
    researcher_conviction: str = "medium"
    researcher_key_factor: str = ""
    # Technical snapshot used for analysis
    tech_summary: str = ""
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


def init_db() -> None:
    SQLModel.metadata.create_all(engine)
    # Lightweight in-place migrations for additive columns. SQLite ignores ALTER
    # TABLE ADD COLUMN if the column exists — but raises OperationalError, so we
    # catch it. Keeps existing DBs working without a manual reset.
    from sqlalchemy import text
    with engine.begin() as conn:
        for stmt in (
            "ALTER TABLE papertrade ADD COLUMN why_summary TEXT DEFAULT ''",
        ):
            try:
                conn.exec_driver_sql(stmt)
            except Exception:
                pass  # column already exists


# ── helpers ───────────────────────────────────────────────────────────────────

def get_active_portfolio(mode: str) -> PaperPortfolio | None:
    with Session(engine) as s:
        results = s.exec(
            select(PaperPortfolio).where(
                PaperPortfolio.is_active == True,
                PaperPortfolio.mode == mode
            )
        ).all()
        return results[0] if results else None


def get_or_create_portfolio(mode: str, initial_capital: float = 20_000.0) -> PaperPortfolio:
    p = get_active_portfolio(mode)
    if p:
        return p
    p = PaperPortfolio(
        name=f"AI Paper Portfolio ({mode.title()})",
        mode=mode,
        initial_capital=initial_capital,
        cash=initial_capital,
    )
    with Session(engine) as s:
        s.add(p)
        s.commit()
        s.refresh(p)
    return p


def get_positions(portfolio_id: str) -> list[PaperPosition]:
    with Session(engine) as s:
        return s.exec(select(PaperPosition).where(PaperPosition.portfolio_id == portfolio_id)).all()


def get_trades(portfolio_id: str) -> list[PaperTrade]:
    with Session(engine) as s:
        return s.exec(
            select(PaperTrade)
            .where(PaperTrade.portfolio_id == portfolio_id)
            .order_by(PaperTrade.executed_at.desc())  # type: ignore[arg-type]
        ).all()


def get_snapshots(portfolio_id: str) -> list[PaperDailySnapshot]:
    with Session(engine) as s:
        return s.exec(
            select(PaperDailySnapshot)
            .where(PaperDailySnapshot.portfolio_id == portfolio_id)
            .order_by(PaperDailySnapshot.date)  # type: ignore[arg-type]
        ).all()


def save_trade(trade: PaperTrade) -> PaperTrade:
    with Session(engine) as s:
        s.add(trade)
        s.commit()
        s.refresh(trade)
    return trade


def update_portfolio_cash(portfolio_id: str, new_cash: float) -> None:
    with Session(engine) as s:
        p = s.get(PaperPortfolio, portfolio_id)
        if p:
            p.cash = new_cash
            s.add(p)
            s.commit()


def upsert_position(pos: PaperPosition) -> None:
    with Session(engine) as s:
        existing = s.exec(
            select(PaperPosition).where(
                PaperPosition.portfolio_id == pos.portfolio_id,
                PaperPosition.ticker == pos.ticker,
                PaperPosition.direction == pos.direction,
            )
        ).first()
        if existing:
            # Average in
            total_qty = existing.quantity + pos.quantity
            existing.avg_entry_price = (
                existing.avg_entry_price * existing.quantity + pos.avg_entry_price * pos.quantity
            ) / total_qty
            existing.quantity = total_qty
            existing.stop_loss = pos.stop_loss
            existing.take_profit = pos.take_profit
            s.add(existing)
        else:
            s.add(pos)
        s.commit()


def close_position(portfolio_id: str, ticker: str, direction: str = "long") -> PaperPosition | None:
    with Session(engine) as s:
        pos = s.exec(
            select(PaperPosition).where(
                PaperPosition.portfolio_id == portfolio_id,
                PaperPosition.ticker == ticker,
                PaperPosition.direction == direction,
            )
        ).first()
        if pos:
            s.delete(pos)
            s.commit()
        return pos


def save_snapshot(snap: PaperDailySnapshot) -> None:
    with Session(engine) as s:
        # Replace today's snapshot if it exists
        existing = s.exec(
            select(PaperDailySnapshot).where(
                PaperDailySnapshot.portfolio_id == snap.portfolio_id,
                PaperDailySnapshot.date == snap.date,
            )
        ).first()
        if existing:
            s.delete(existing)
            s.commit()
        s.add(snap)
        s.commit()


def save_analysis(analysis: PaperTradeAnalysis) -> None:
    with Session(engine) as s:
        existing = s.exec(select(PaperTradeAnalysis).where(PaperTradeAnalysis.trade_id == analysis.trade_id)).first()
        if existing:
            return   # already exists
        s.add(analysis)
        s.commit()


def get_analysis(trade_id: str) -> PaperTradeAnalysis | None:
    with Session(engine) as s:
        return s.exec(select(PaperTradeAnalysis).where(PaperTradeAnalysis.trade_id == trade_id)).first()


def get_analyses_for_portfolio(portfolio_id: str) -> list[PaperTradeAnalysis]:
    with Session(engine) as s:
        return s.exec(select(PaperTradeAnalysis).where(PaperTradeAnalysis.portfolio_id == portfolio_id)).all()


def reset_portfolio(portfolio_id: str) -> None:
    """Reset paper portfolio to initial state."""
    with Session(engine) as s:
        p = s.get(PaperPortfolio, portfolio_id)
        if p:
            p.cash = p.initial_capital
            p.started_at = datetime.utcnow().isoformat()
            s.add(p)
        # Delete all positions, trades, snapshots, analyses
        for model in [PaperPosition, PaperTrade, PaperDailySnapshot, PaperTradeAnalysis]:
            rows = s.exec(select(model).where(model.portfolio_id == portfolio_id)).all()  # type: ignore[attr-defined]
            for row in rows:
                s.delete(row)
        s.commit()
