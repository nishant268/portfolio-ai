"""
Paper Trading AI Agent.
Runs a full technical + fundamental + sentiment analysis pass on each watchlist stock,
then uses an LLM to decide BUY / SELL / HOLD with full detailed reasoning.
All trades execute virtually against live NSE prices via yfinance.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, date
from typing import Any

import yfinance as yf

from backend.models.config import AppConfig, load_config
from backend.models.paper_trade import (
    PaperDailySnapshot, PaperPortfolio, PaperPosition, PaperTrade,
    close_position, get_or_create_portfolio, get_positions, get_trades,
    save_snapshot, save_trade, update_portfolio_cash, upsert_position,
)
from backend.scrapers.nse import nse
from backend.scrapers.news import fetch_all_news
from portfolio_ai.data.market_data import compute_technicals, get_fundamentals, get_news_headlines

# ── Watchlists ────────────────────────────────────────────────────────────────

# ── Complete NIFTY 50 watchlist (live as of 2026) ─────────────────────────────
# Source: NSE live data — excludes ETERNAL (Zomato rename, excluded by user)
# and TMPV (index placeholder, not tradeable)

# Investor mode: fundamentals-first — all 48 NIFTY 50 tradeable constituents
INVESTOR_WATCHLIST = [
    # Banking & Finance
    "HDFCBANK", "ICICIBANK", "KOTAKBANK", "SBIN", "AXISBANK",
    "BAJFINANCE", "BAJAJFINSV", "HDFCLIFE", "SBILIFE", "SHRIRAMFIN",
    # IT & Technology
    "TCS", "INFY", "HCLTECH", "WIPRO", "TECHM",
    # Reliance & Conglomerates
    "RELIANCE", "ADANIENT", "ADANIPORTS", "LT", "JIOFIN",
    # Consumer & FMCG
    "HINDUNILVR", "ITC", "NESTLEIND", "BRITANNIA", "TATACONSUM",
    # Auto
    "MARUTI", "BAJAJ-AUTO", "EICHERMOT", "M&M",
    # Pharma & Healthcare
    "SUNPHARMA", "DRREDDY", "CIPLA", "APOLLOHOSP", "MAXHEALTH",
    # Metals & Mining
    "TATASTEEL", "JSWSTEEL", "HINDALCO", "COALINDIA",
    # Energy & Infrastructure
    "ONGC", "NTPC", "POWERGRID", "BEL",
    # Cement & Materials
    "ULTRACEMCO", "GRASIM",
    # Consumer Discretionary
    "TITAN", "ASIANPAINT", "TRENT", "INDIGO",
]

# Trader mode: F&O eligible, high-volume, strong technical signals
TRADER_WATCHLIST = [
    # Most liquid — highest F&O OI
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK",
    "SBIN", "BAJFINANCE", "AXISBANK", "KOTAKBANK", "BHARTIARTL",
    # Metals & cyclicals — strong momentum
    "TATASTEEL", "JSWSTEEL", "HINDALCO", "COALINDIA", "ONGC",
    # Infrastructure & PSU — high beta
    "NTPC", "POWERGRID", "BEL", "ADANIENT", "LT",
    # Auto — trending
    "MARUTI", "BAJAJ-AUTO", "M&M", "EICHERMOT",
    # IT — range-bound trades
    "HCLTECH", "WIPRO", "TECHM",
    # Consumer — defensives
    "ITC", "HINDUNILVR", "TITAN", "TRENT",
]

MAX_POSITION_PCT = 0.12       # max 12% of portfolio per stock
MIN_CASH_PCT = 0.15           # keep at least 15% in cash
MAX_POSITIONS = 12            # increased from 10
STOP_LOSS_PCT = 0.08
TAKE_PROFIT_PCT = 0.20
COOLDOWN_MINUTES = 15         # block re-entry for a ticker for N min after an auto-exit (prevents stop-loss churn)


def _yf_ticker(symbol: str) -> str:
    return f"{symbol}.NS"


def _get_live_price(symbol: str) -> float:
    try:
        t = yf.Ticker(_yf_ticker(symbol))
        price = t.fast_info.last_price
        return float(price) if price else 0.0
    except Exception:
        return 0.0


def _get_nifty_price() -> float:
    try:
        t = yf.Ticker("^NSEI")
        return float(t.fast_info.last_price or 0)
    except Exception:
        return 0.0


async def _gather_stock_data(ticker: str) -> dict[str, Any]:
    """Gather all technical + fundamental + news data for one stock."""
    loop = asyncio.get_event_loop()

    def _fetch():
        price = _get_live_price(ticker)
        nse_sym = f"{ticker}.NS"   # yfinance requires .NS suffix for NSE stocks
        try:
            tech = compute_technicals(nse_sym)
        except Exception:
            tech = {}
        try:
            fund = get_fundamentals(nse_sym)
        except Exception:
            fund = {}
        try:
            headlines = get_news_headlines(ticker, max_items=3)
        except Exception:
            headlines = []
        return price, tech, fund, headlines

    price, tech, fund, headlines = await loop.run_in_executor(None, _fetch)

    return {
        "ticker": ticker,
        "price": price,
        "rsi": tech.get("rsi_14", 50),
        "macd": tech.get("macd", 0),
        "macd_signal": tech.get("macd_signal", 0),
        "macd_hist": tech.get("macd_histogram", 0),
        "bb_pct": tech.get("bb_pct_b", 0.5),
        "price_vs_sma50": tech.get("price_vs_sma50", 0),
        "price_vs_sma200": tech.get("price_vs_sma200", 0),
        "golden_cross": tech.get("golden_cross", "no"),
        "pe_ratio": fund.get("pe_ratio"),
        "forward_pe": fund.get("forward_pe"),
        "roe": fund.get("roe"),
        "revenue_growth": fund.get("revenue_growth"),
        "debt_to_equity": fund.get("debt_to_equity"),
        "52w_high": fund.get("52w_high"),
        "52w_low": fund.get("52w_low"),
        "analyst_target": fund.get("analyst_target"),
        "recommendation": fund.get("recommendation"),
        "profit_margin": fund.get("profit_margin"),
        "headlines": headlines,
    }


def _rule_based_decide(
    portfolio: PaperPortfolio,
    stock_data: list[dict[str, Any]],
    nifty_pct: float,
    nifty_bank_pct: float,
    vix: float,
) -> dict[str, Any]:
    """
    5-analyst rule-based decision engine — zero LLM calls.
    Each stock runs through: Technical, Fundamental, Momentum, Sentiment, Market analysts.
    Scores are combined with mode-adjusted weights → BUY / SELL / HOLD.
    """
    from backend.agents.rule_based_trader import (
        technical_analyst, fundamental_analyst, momentum_analyst,
        sentiment_analyst, market_analyst, make_final_decision,
    )

    nifty_direction = f"NIFTY {'+' if nifty_pct >= 0 else ''}{nifty_pct:.2f}% | BANK {'+' if nifty_bank_pct >= 0 else ''}{nifty_bank_pct:.2f}% | VIX {vix:.1f}"
    decisions = []

    for s in stock_data:
        price = s.get("price", 0)
        if price <= 0:
            continue

        headlines = s.get("headlines", [])

        # Run all 5 analysts
        t_score, t_reason = technical_analyst(s)
        f_score, f_reason = fundamental_analyst({**s, "price": price})
        m_score, m_reason = momentum_analyst(s)
        sent_score, sent_reason = sentiment_analyst(headlines, vix)
        mkt_score, mkt_reason = market_analyst(nifty_pct, nifty_bank_pct, None)

        decision = make_final_decision(
            ticker=s["ticker"],
            tech=t_score, tech_reason=t_reason,
            fund=f_score, fund_reason=f_reason,
            mom=m_score, mom_reason=m_reason,
            sent=sent_score, sent_reason=sent_reason,
            mkt=mkt_score, mkt_reason=mkt_reason,
            mode=portfolio.mode,
            price=price,
            stop_loss_pct=STOP_LOSS_PCT,
            take_profit_pct=TAKE_PROFIT_PCT,
        )

        # Only include non-HOLD decisions
        if decision["action"] != "HOLD":
            decisions.append({**decision, "quantity": _calc_quantity(portfolio, price)})

    # Sort by confidence descending
    decisions.sort(key=lambda d: d["confidence"], reverse=True)

    market_view = (
        f"Market: {nifty_direction}. "
        f"{'Bullish market conditions — favour longs.' if nifty_pct > 0 else 'Bearish market conditions — cautious stance.'} "
        f"{'High VIX signals fear — reduce position sizes.' if vix > 20 else 'Normal volatility environment.'}"
    )

    return {"market_view": market_view, "decisions": decisions[:6]}  # top 6 by conviction


async def _analyse_trade(
    trade_id: str, portfolio_id: str, ticker: str, action: str,
    price: float, quantity: float, dec: dict[str, Any],
    stock: dict[str, Any], nifty_pct: float, vix: float, market_view: str,
) -> None:
    """Background Claude call — generates bull/bear/researcher analysis for one trade."""
    try:
        from backend.agents.trade_analyst import generate_trade_analysis
        await generate_trade_analysis(
            trade_id=trade_id, portfolio_id=portfolio_id,
            ticker=ticker, action=action, price=price, quantity=quantity,
            rule_signal=dec.get("signal", ""),
            rule_score=float(dec.get("combined_score", 0)),
            stock_data=stock,
            nifty_pct=nifty_pct, vix=vix, market_view=market_view,
        )
    except Exception:
        pass   # analysis never blocks trades


def _calc_quantity(portfolio: PaperPortfolio, price: float) -> int:
    """Calculate buy quantity within capital constraints."""
    available = portfolio.cash * (1 - MIN_CASH_PCT)
    max_invest = portfolio.initial_capital * MAX_POSITION_PCT
    invest = min(available, max_invest)
    qty = int(invest // price)
    return max(qty, 1) if invest >= price else 0


# ── Main trading session ──────────────────────────────────────────────────────

async def run_trading_session(mode: str = "investor", initial_capital: float = 1_000_000.0) -> dict[str, Any]:
    """
    Full trading session:
    1. Check existing positions for stop-loss / take-profit
    2. Gather data for watchlist
    3. LLM decides trades
    4. Execute virtually
    5. Record daily snapshot
    Returns a summary of the session.
    """
    cfg = load_config()
    portfolio = get_or_create_portfolio(mode, initial_capital)
    positions = get_positions(portfolio.id)
    watchlist = TRADER_WATCHLIST if mode == "trader" else INVESTOR_WATCHLIST

    # ── Step 1: Fetch market context ──────────────────────────────────────────
    indices: list[dict[str, Any]] = []
    try:
        indices = await nse.all_indices()
        key_idx = [i for i in indices if i.get("indexSymbol") in
                   ["NIFTY 50", "NIFTY BANK", "INDIA VIX"]]
        market_context = "\n".join(
            f"  {i['indexSymbol']}: {i['last']} ({'+' if i['percentChange'] >= 0 else ''}{i['percentChange']}%)"
            for i in key_idx
        )
    except Exception:
        market_context = "  Market data unavailable"

    try:
        news = await fetch_all_news()
        news_summary = "\n".join(f"  • {n['title']}" for n in news[:6])
    except Exception:
        news_summary = "  News unavailable"

    # ── Step 2: Auto stop-loss / take-profit on existing positions ────────────
    auto_exits: list[dict[str, Any]] = []
    loop = asyncio.get_event_loop()

    for pos in positions:
        live_price = await loop.run_in_executor(None, _get_live_price, pos.ticker)
        if live_price <= 0:
            continue

        triggered = None
        if pos.direction == "long":
            if pos.stop_loss > 0 and live_price <= pos.stop_loss:
                triggered = ("STOP_LOSS", "Price hit stop-loss level. Exiting to protect capital.")
            elif pos.take_profit > 0 and live_price >= pos.take_profit:
                triggered = ("TAKE_PROFIT", "Price reached take-profit target. Locking in gains.")
        elif pos.direction == "short":
            if pos.stop_loss > 0 and live_price >= pos.stop_loss:
                triggered = ("STOP_LOSS", "Price hit stop-loss on short position. Covering to limit loss.")
            elif pos.take_profit > 0 and live_price <= pos.take_profit:
                triggered = ("TAKE_PROFIT", "Price reached downside target on short. Covering for profit.")

        if triggered:
            reason_type, reason_text = triggered
            pnl = (live_price - pos.avg_entry_price) * pos.quantity * (1 if pos.direction == "long" else -1)
            proceeds = live_price * pos.quantity

            pct_move = (pnl / (pos.avg_entry_price * pos.quantity)) * 100
            why = (
                f"{reason_type} · entry ₹{pos.avg_entry_price:.2f} → exit ₹{live_price:.2f} "
                f"({pct_move:+.1f}%) · P&L ₹{pnl:+,.0f}"
            )
            t = PaperTrade(
                portfolio_id=portfolio.id,
                ticker=pos.ticker,
                action="SELL" if pos.direction == "long" else "COVER",
                quantity=pos.quantity,
                price=live_price,
                trade_value=proceeds,
                pnl=pnl,
                signal=reason_type,
                reasoning=f"AUTO {reason_type}: {reason_text} "
                          f"Entry ₹{pos.avg_entry_price:.2f} → Exit ₹{live_price:.2f}. "
                          f"P&L: ₹{pnl:+,.2f} ({pct_move:+.1f}%)",
                why_summary=why,
                session_market_view="Auto exit triggered",
            )
            save_trade(t)
            close_position(portfolio.id, pos.ticker, pos.direction)
            # Proceeds model: SELL adds cash (receive sale proceeds); COVER subtracts (pay to buy back)
            if pos.direction == "long":
                portfolio.cash += proceeds
            else:
                portfolio.cash -= proceeds
            update_portfolio_cash(portfolio.id, portfolio.cash)
            auto_exits.append({"ticker": pos.ticker, "reason": reason_type, "pnl": pnl})

    # Refresh positions after auto-exits
    positions = get_positions(portfolio.id)

    # ── Step 3: Gather stock data for watchlist ────────────────────────────────
    # Exclude already-held tickers at max capacity
    held_tickers = {p.ticker for p in positions}
    # Proceeds model: long positions add to portfolio value; short positions are liabilities (subtract)
    portfolio_value = portfolio.cash + sum(
        p.avg_entry_price * p.quantity * (1 if p.direction == "long" else -1)
        for p in positions
    )
    cash_pct = portfolio.cash / portfolio_value if portfolio_value > 0 else 1.0

    candidates = list(watchlist[:20])  # analyse full watchlist (runs in parallel)

    tasks = [_gather_stock_data(t) for t in candidates]
    stock_data = await asyncio.gather(*tasks, return_exceptions=True)
    stock_data = [s for s in stock_data if isinstance(s, dict) and s.get("price", 0) > 0]

    # ── Step 4: Rule-based decisions (zero LLM / zero API quota) ─────────────
    nifty_pct      = next((i.get("percentChange", 0) for i in indices if i.get("indexSymbol") == "NIFTY 50"), 0.0)
    nifty_bank_pct = next((i.get("percentChange", 0) for i in indices if i.get("indexSymbol") == "NIFTY BANK"), 0.0)
    vix            = next((i.get("last", 15) for i in indices if i.get("indexSymbol") == "INDIA VIX"), 15.0)

    rule_result = _rule_based_decide(
        portfolio=portfolio,
        stock_data=stock_data,
        nifty_pct=float(nifty_pct),
        nifty_bank_pct=float(nifty_bank_pct),
        vix=float(vix),
    )

    market_view = rule_result.get("market_view", "")
    decisions   = rule_result.get("decisions", [])

    # ── Step 4.5: Build re-entry cooldown map ─────────────────────────────────
    # If a ticker was auto-exited (STOP_LOSS / TAKE_PROFIT) in the last
    # COOLDOWN_MINUTES, skip new entries for it — prevents the immediate
    # re-short churn pattern.
    from datetime import datetime as _dt, timedelta as _td
    cooldown_until: dict[str, _dt] = {}
    cooldown_cutoff = _dt.utcnow() - _td(minutes=COOLDOWN_MINUTES)
    for tr in get_trades(portfolio.id):
        if tr.action not in ("SELL", "COVER"):
            continue
        if tr.signal not in ("STOP_LOSS", "TAKE_PROFIT"):
            continue
        try:
            exit_at = _dt.fromisoformat(tr.executed_at)
        except Exception:
            continue
        if exit_at < cooldown_cutoff:
            continue
        prev = cooldown_until.get(tr.ticker)
        end_at = exit_at + _td(minutes=COOLDOWN_MINUTES)
        if not prev or end_at > prev:
            cooldown_until[tr.ticker] = end_at

    held_tickers = {p.ticker for p in positions}

    # ── Step 5: Execute decisions ─────────────────────────────────────────────
    executed_trades: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    stock_price_map = {s["ticker"]: s for s in stock_data}
    now_utc = _dt.utcnow()

    for dec in decisions:
        ticker = dec.get("ticker", "")
        action = dec.get("action", "HOLD").upper()
        quantity = int(dec.get("quantity", 0))

        if action == "HOLD" or quantity <= 0 or not ticker:
            continue

        # Skip new entries that violate cooldown or already have a position
        if action in ("BUY", "SHORT"):
            cd_end = cooldown_until.get(ticker)
            if cd_end and cd_end > now_utc:
                mins_left = int((cd_end - now_utc).total_seconds() // 60) + 1
                skipped.append({"ticker": ticker, "reason": f"cooldown {mins_left}m after recent stop-loss"})
                continue
            if ticker in held_tickers:
                skipped.append({"ticker": ticker, "reason": "already have an open position"})
                continue

        stock = stock_price_map.get(ticker)
        if not stock:
            continue

        live_price = stock["price"]
        if live_price <= 0:
            continue

        if action == "SHORT":
            stop_loss   = float(dec.get("stop_loss",   live_price * (1 + STOP_LOSS_PCT)))
            take_profit = float(dec.get("take_profit", live_price * (1 - TAKE_PROFIT_PCT)))
        else:
            stop_loss   = float(dec.get("stop_loss",   live_price * (1 - STOP_LOSS_PCT)))
            take_profit = float(dec.get("take_profit", live_price * (1 + TAKE_PROFIT_PCT)))
        full_reasoning = dec.get("reasoning", "")  # rule-based engine already built full reasoning

        tech_snapshot = json.dumps({
            k: dec.get("scores", {}).get(k) or stock.get(k)
            for k in ["rsi", "macd_hist", "bb_pct", "price_vs_sma50", "price_vs_sma200", "golden_cross", "pe_ratio", "roe"]
        })

        if action in ("BUY", "SHORT"):
            # Use pre-calculated quantity from rule engine, enforce capital guards
            max_invest  = portfolio_value * MAX_POSITION_PCT
            available   = portfolio.cash - portfolio_value * MIN_CASH_PCT
            if available < live_price:
                continue
            actual_qty = min(quantity, int(available // live_price))
            if actual_qty <= 0:
                continue
            cost = actual_qty * live_price

            t = PaperTrade(
                portfolio_id=portfolio.id,
                ticker=ticker,
                action=action,
                quantity=actual_qty,
                price=live_price,
                trade_value=cost,
                pnl=0.0,
                signal=dec.get("signal", "BUY"),
                reasoning=full_reasoning,
                why_summary=dec.get("why_summary", ""),
                technicals_snapshot=tech_snapshot,
                session_market_view=market_view,
            )
            save_trade(t)
            # Fire-and-forget Claude analysis (doesn't block trade execution)
            asyncio.create_task(_analyse_trade(
                trade_id=t.id, portfolio_id=portfolio.id,
                ticker=ticker, action=action, price=live_price, quantity=actual_qty,
                dec=dec, stock=stock, nifty_pct=nifty_pct, vix=vix, market_view=market_view,
            ))

            new_pos = PaperPosition(
                portfolio_id=portfolio.id,
                ticker=ticker,
                quantity=actual_qty,
                avg_entry_price=live_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                direction="long" if action == "BUY" else "short",
            )
            upsert_position(new_pos)
            # Proceeds model: BUY spends cash; SHORT receives proceeds (short sale proceeds go into cash)
            if action == "BUY":
                portfolio.cash -= cost
            else:  # SHORT
                portfolio.cash += cost
            update_portfolio_cash(portfolio.id, portfolio.cash)

            executed_trades.append({
                "action": action, "ticker": ticker, "qty": actual_qty,
                "price": live_price, "cost": cost, "pnl": 0.0,
                "reasoning": full_reasoning, "signal": dec.get("signal"),
                "why_summary": dec.get("why_summary", ""),
            })

        elif action in ("SELL", "COVER"):
            pos = next((p for p in positions if p.ticker == ticker), None)
            if not pos:
                continue
            sell_qty = min(quantity, int(pos.quantity))
            proceeds = sell_qty * live_price
            pnl = (live_price - pos.avg_entry_price) * sell_qty * (1 if pos.direction == "long" else -1)

            t = PaperTrade(
                portfolio_id=portfolio.id,
                ticker=ticker,
                action=action,
                quantity=sell_qty,
                price=live_price,
                trade_value=proceeds,
                pnl=pnl,
                signal=dec.get("signal", "SELL"),
                reasoning=full_reasoning,
                why_summary=dec.get("why_summary", ""),
                technicals_snapshot=tech_snapshot,
                session_market_view=market_view,
            )
            save_trade(t)
            asyncio.create_task(_analyse_trade(
                trade_id=t.id, portfolio_id=portfolio.id,
                ticker=ticker, action=action, price=live_price, quantity=sell_qty,
                dec=dec, stock=stock, nifty_pct=nifty_pct, vix=vix, market_view=market_view,
            ))

            if sell_qty >= pos.quantity:
                close_position(portfolio.id, ticker, pos.direction)
            else:
                pos.quantity -= sell_qty
                upsert_position(pos)

            # Proceeds model: SELL receives cash; COVER pays cash to buy back shares
            if pos.direction == "long":
                portfolio.cash += proceeds
            else:
                portfolio.cash -= proceeds
            update_portfolio_cash(portfolio.id, portfolio.cash)

            executed_trades.append({
                "action": action, "ticker": ticker, "qty": sell_qty,
                "price": live_price, "proceeds": proceeds, "pnl": pnl,
                "reasoning": full_reasoning, "signal": dec.get("signal"),
                "why_summary": dec.get("why_summary", ""),
            })

    # ── Step 6: Daily snapshot ────────────────────────────────────────────────
    final_positions = get_positions(portfolio.id)

    async def _fetch_pos_value(p) -> float:
        price = await loop.run_in_executor(None, _get_live_price, p.ticker)
        val = (price if price > 0 else p.avg_entry_price) * p.quantity
        # Proceeds model: long position is an asset (+); short is a liability (-)
        return val if p.direction == "long" else -val

    pos_values = await asyncio.gather(*[_fetch_pos_value(p) for p in final_positions])
    positions_value = sum(pos_values)
    total_value = portfolio.cash + positions_value
    total_pnl = total_value - portfolio.initial_capital
    total_pnl_pct = (total_pnl / portfolio.initial_capital) * 100

    nifty_price = await loop.run_in_executor(None, _get_nifty_price)

    # Daily P&L from previous snapshot
    from backend.models.paper_trade import get_snapshots
    snaps = get_snapshots(portfolio.id)
    prev_value = snaps[-1].portfolio_value if snaps else portfolio.initial_capital
    daily_pnl = total_value - prev_value
    daily_pnl_pct = (daily_pnl / prev_value) * 100 if prev_value else 0

    snap = PaperDailySnapshot(
        portfolio_id=portfolio.id,
        date=date.today().isoformat(),
        portfolio_value=total_value,
        cash=portfolio.cash,
        positions_value=positions_value,
        daily_pnl=daily_pnl,
        daily_pnl_pct=daily_pnl_pct,
        total_pnl=total_pnl,
        total_pnl_pct=total_pnl_pct,
        nifty_value=nifty_price,
    )
    save_snapshot(snap)

    return {
        "session_date": date.today().isoformat(),
        "market_view": market_view,
        "portfolio_value": total_value,
        "cash": portfolio.cash,
        "positions_value": positions_value,
        "daily_pnl": daily_pnl,
        "daily_pnl_pct": daily_pnl_pct,
        "total_pnl": total_pnl,
        "total_pnl_pct": total_pnl_pct,
        "auto_exits": auto_exits,
        "executed_trades": executed_trades,
        "trades_count": len(executed_trades),
        "skipped": skipped,
        "active_positions": len(final_positions),
    }
