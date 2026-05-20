from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException

from backend.models.paper_trade import (
    get_or_create_portfolio, get_positions, get_snapshots, get_trades,
    init_db, reset_portfolio, get_active_portfolio,
    get_analysis, get_analyses_for_portfolio,
)

router = APIRouter(prefix="/api/paper", tags=["paper-trading"])

_running: set[str] = set()
_session_results: dict[str, dict] = {}


@router.get("/portfolio/{mode}")
async def get_portfolio(mode: str):
    if mode not in ("investor", "trader"):
        raise HTTPException(400, "mode must be investor or trader")
    p = get_or_create_portfolio(mode)
    positions = get_positions(p.id)
    snaps = get_snapshots(p.id)
    trades = get_trades(p.id)

    # Enrich positions with live prices — fetch all concurrently (non-blocking)
    from backend.agents.paper_trader import _get_live_price
    loop = asyncio.get_event_loop()

    async def _fetch_price(pos):
        try:
            price = await loop.run_in_executor(None, _get_live_price, pos.ticker)
        except Exception:
            price = 0.0
        return price if price > 0 else pos.avg_entry_price  # fallback to entry when market closed

    live_prices = await asyncio.gather(*[_fetch_price(p) for p in positions])

    enriched = []
    for pos, live in zip(positions, live_prices):
        cost = pos.avg_entry_price * pos.quantity
        mv = live * pos.quantity
        pnl = (mv - cost) if pos.direction == "long" else (cost - mv)
        enriched.append({
            **pos.model_dump(),
            "current_price": live,
            "market_value": mv,
            # Proceeds model: long is an asset; short is a liability (negative contribution to total value)
            "portfolio_contribution": mv if pos.direction == "long" else -mv,
            "unrealized_pnl": pnl,
            "unrealized_pnl_pct": (pnl / cost * 100) if cost else 0,
        })

    # Calculate stats
    total_realised = sum(t.pnl for t in trades)
    wins = [t for t in trades if t.pnl > 0]
    losses = [t for t in trades if t.pnl < 0]
    win_rate = len(wins) / len([t for t in trades if t.action in ("SELL", "COVER")]) * 100 \
               if any(t.action in ("SELL", "COVER") for t in trades) else 0

    days_running = len(set(s.date for s in snaps))

    return {
        "portfolio": p.model_dump(),
        "positions": enriched,
        "snapshots": [s.model_dump() for s in snaps],
        "stats": {
            "total_trades": len(trades),
            "buy_trades": len([t for t in trades if t.action in ("BUY", "SHORT")]),
            "sell_trades": len([t for t in trades if t.action in ("SELL", "COVER")]),
            "total_realised_pnl": total_realised,
            "win_rate": round(win_rate, 1),
            "wins": len(wins),
            "losses": len(losses),
            "avg_win": (sum(t.pnl for t in wins) / len(wins)) if wins else 0,
            "avg_loss": (sum(t.pnl for t in losses) / len(losses)) if losses else 0,
            "days_running": days_running,
            "best_trade": max((t.pnl for t in trades), default=0),
            "worst_trade": min((t.pnl for t in trades), default=0),
        },
    }


@router.get("/analysis/{trade_id}")
async def get_trade_analysis(trade_id: str):
    """Get bull/bear/researcher analysis for a specific trade."""
    a = get_analysis(trade_id)
    if not a:
        return {"analysis": None, "pending": True}
    import json as _json
    return {
        "analysis": {
            **a.model_dump(),
            "bull_catalysts": _json.loads(a.bull_catalysts),
            "bear_risks":     _json.loads(a.bear_risks),
        },
        "pending": False,
    }


@router.get("/all-analyses/{mode}")
async def get_all_analyses(mode: str):
    p = get_active_portfolio(mode)
    if not p:
        return {"analyses": {}}
    import json as _json
    result = {}
    for a in get_analyses_for_portfolio(p.id):
        result[a.trade_id] = {
            **a.model_dump(),
            "bull_catalysts": _json.loads(a.bull_catalysts),
            "bear_risks":     _json.loads(a.bear_risks),
        }
    return {"analyses": result}


@router.get("/trades/{mode}")
async def get_trade_history(mode: str, limit: int = 500):
    p = get_active_portfolio(mode)
    if not p:
        return {"trades": []}
    trades = get_trades(p.id)[:limit]
    result = []
    for t in trades:
        d = t.model_dump()
        try:
            d["technicals"] = json.loads(t.technicals_snapshot)
        except Exception:
            d["technicals"] = {}
        result.append(d)
    return {"trades": result}


@router.post("/run/{mode}")
async def run_session(mode: str, background_tasks: BackgroundTasks, capital: float = 1_000_000.0):
    if mode not in ("investor", "trader"):
        raise HTTPException(400, "mode must be investor or trader")
    if mode in _running:
        return {"status": "already_running", "message": "A trading session is already in progress"}

    async def _run():
        _running.add(mode)
        try:
            from backend.agents.paper_trader import run_trading_session
            result = await run_trading_session(mode=mode, initial_capital=capital)
            _session_results[mode] = {"status": "done", **result}
        except Exception as e:
            err = str(e)
            if "429" in err or "RESOURCE_EXHAUSTED" in err or "quota" in err.lower():
                _session_results[mode] = {
                    "status": "error",
                    "error": "Rate limit / quota exhausted on your AI provider. Wait a few minutes and try again, or enable billing on your Google AI Studio account, or switch to OpenAI/Anthropic in Setup → Step 3.",
                }
            else:
                _session_results[mode] = {"status": "error", "error": err}
        finally:
            _running.discard(mode)

    background_tasks.add_task(_run)
    _session_results[mode] = {"status": "running"}
    return {"status": "started", "message": "AI trading session started in background"}


@router.get("/session-status/{mode}")
async def session_status(mode: str):
    return _session_results.get(mode, {"status": "idle"})


@router.post("/reset/{mode}")
async def reset(mode: str):
    p = get_active_portfolio(mode)
    if p:
        reset_portfolio(p.id)
    return {"ok": True, "message": f"{mode} paper portfolio reset to initial capital"}
