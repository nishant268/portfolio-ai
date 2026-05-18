from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from backend.models.config import load_config
from backend.utils import cache as llm_cache
from portfolio_ai.data.market_data import compute_technicals, get_fundamentals, get_news_headlines
from portfolio_ai.models.portfolio import AssetClass, Position

router = APIRouter(prefix="/api/analysis", tags=["analysis"])

# In-memory cache for analysis results (keyed by ticker)
_analysis_cache: dict[str, dict[str, Any]] = {}
_running: set[str] = set()


# ── Trade Validator: ONE Claude call per order, minimal tokens ────────────────

class TradeValidateRequest(BaseModel):
    ticker: str
    action: str          # BUY | SELL
    quantity: float
    price: float
    rule_signal: str     # from rule engine: STRONG_BUY / BUY / SELL etc.
    rule_score: float    # combined score
    rule_reasoning: str  # top 200 chars of rule reasoning


@router.post("/validate-trade")
async def validate_trade(req: TradeValidateRequest) -> dict[str, Any]:
    """
    Single Claude call to validate a trade proposed by the rule engine.
    Cached for 30 min — same trade parameters = no repeat call.
    Only called when user clicks 'Get Claude's Opinion' before placing order.
    """
    cfg = load_config()

    # Build a minimal cache key
    cache_key = f"{req.ticker}:{req.action}:{req.rule_signal}:{round(req.price, -1)}"
    cached = llm_cache.get(cache_key)
    if cached:
        return {**cached, "cached": True}

    if not cfg.llm_api_key:
        return {
            "verdict": "NO_KEY",
            "confidence": 0,
            "opinion": "No API key configured. Using rule engine signal only.",
            "cached": False,
        }

    # Minimal prompt — keep tokens low (< 300 input, < 150 output)
    prompt = (
        f"Stock: {req.ticker} | Action: {req.action} | Price: ₹{req.price:.2f}\n"
        f"Rule engine: {req.rule_signal} (score {req.rule_score:+.1f}/10)\n"
        f"Analysis: {req.rule_reasoning[:250]}\n\n"
        f"In 2-3 sentences, should I {req.action} {req.quantity:.0f} shares of {req.ticker}? "
        f"Reply: CONFIRM or REJECT, then brief reasoning. Be direct."
    )

    try:
        import asyncio as _aio
        import httpx

        # ── Use direct HTTP for Google (avoids tenacity retry hanging) ─────────
        if cfg.llm_provider == "google":
            model = cfg.llm_model or "gemini-2.0-flash-lite"
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={cfg.llm_api_key}"
            body = {
                "contents": [{"parts": [{"text": f"You are a concise NSE analyst. {prompt}"}]}],
                "generationConfig": {"maxOutputTokens": 150, "temperature": 0.1},
            }
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.post(url, json=body)
            if r.status_code == 429:
                return {"verdict": "RATE_LIMITED", "confidence": 0.5,
                        "opinion": f"Rate limited. Rule engine says {req.rule_signal} — trust that.", "cached": False}
            if r.status_code != 200:
                return {"verdict": "ERROR", "confidence": 0,
                        "opinion": f"API error {r.status_code}. Use rule engine signal: {req.rule_signal}", "cached": False}
            text = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()

        # ── OpenAI / Anthropic via direct HTTP ────────────────────────────────
        elif cfg.llm_provider in ("openai", "anthropic"):
            from langchain_core.messages import HumanMessage, SystemMessage
            from portfolio_ai.agents.portfolio_evaluator import _make_llm
            llm = _make_llm(cfg.llm_provider, cfg.llm_model, temperature=0.1, api_key=cfg.llm_api_key or None)
            resp = await _aio.wait_for(
                llm.ainvoke([
                    SystemMessage(content="You are a concise Indian stock market analyst. 2 sentences max."),
                    HumanMessage(content=prompt),
                ]),
                timeout=10.0,
            )
            text = resp.content.strip()
        else:
            return {"verdict": "UNSUPPORTED", "confidence": 0.5,
                    "opinion": f"Provider {cfg.llm_provider} not supported for trade validation.", "cached": False}

        verdict = "CONFIRM" if "CONFIRM" in text.upper() else "REJECT" if "REJECT" in text.upper() else "NEUTRAL"
        result = {
            "verdict": verdict,
            "confidence": 0.8 if verdict != "NEUTRAL" else 0.5,
            "opinion": text,
            "cached": False,
            "tokens_used": len(prompt.split()) + len(text.split()),  # rough estimate
        }
        llm_cache.set(cache_key, result, ttl_seconds=1800)   # cache 30 min
        return result

    except TimeoutError:
        return {"verdict": "TIMEOUT", "confidence": 0.5,
                "opinion": f"AI took too long. Rule engine says **{req.rule_signal}** — you can trust that signal.", "cached": False}
    except Exception as exc:
        err = str(exc)
        if "429" in err or "quota" in err.lower():
            return {"verdict": "RATE_LIMITED", "confidence": 0.5,
                    "opinion": f"Rate limited. Rule engine says **{req.rule_signal}** — use that.", "cached": False}
        return {"verdict": "ERROR", "confidence": 0, "opinion": f"Error: {err[:100]}", "cached": False}


@router.get("/cache-stats")
async def cache_stats():
    """Show how many cached responses are saving API calls."""
    return llm_cache.stats()


@router.get("/quick/{ticker}")
async def quick_analysis(ticker: str) -> dict[str, Any]:
    """Fast technical + fundamentals snapshot (no LLM, instant)."""
    try:
        fundamentals = get_fundamentals(ticker)
        technicals = compute_technicals(ticker)
        news = get_news_headlines(ticker, max_items=5)

        # Simple rule-based signal
        rsi = technicals.get("rsi_14", 50)
        macd_hist = technicals.get("macd_histogram", 0)
        pnl_pct = fundamentals.get("revenue_growth", 0) or 0

        if rsi > 72 and macd_hist < 0:
            quick_signal = "SELL"
        elif rsi < 35 and macd_hist > 0:
            quick_signal = "BUY"
        elif rsi > 65:
            quick_signal = "WEAK_SELL"
        elif rsi < 45:
            quick_signal = "WEAK_BUY"
        else:
            quick_signal = "HOLD"

        return {
            "ticker": ticker,
            "quick_signal": quick_signal,
            "fundamentals": fundamentals,
            "technicals": technicals,
            "recent_headlines": news,
        }
    except Exception as exc:
        raise HTTPException(500, str(exc))


@router.post("/deep/{ticker}")
async def start_deep_analysis(ticker: str, background_tasks: BackgroundTasks) -> dict[str, Any]:
    """Kick off the full 7-agent LangGraph pipeline (async, non-blocking)."""
    if ticker in _running:
        return {"status": "running", "ticker": ticker}

    cfg = load_config()

    async def _run():
        _running.add(ticker)
        try:
            from portfolio_ai.agents.portfolio_evaluator import evaluate_position
            import yfinance as yf

            fast = yf.Ticker(ticker).fast_info
            price = float(getattr(fast, "last_price", 0) or 0)
            pos = Position(
                ticker=ticker,
                asset_class=AssetClass.STOCK,
                quantity=1,
                avg_cost=price,
                current_price=price,
            )
            result = await evaluate_position(pos, provider=cfg.llm_provider, model=cfg.llm_model)
            _analysis_cache[ticker] = {
                "status": "done",
                "ticker": ticker,
                "signal": result.signal.value,
                "confidence": result.confidence,
                "analyst_summary": result.analyst_summary,
                "target_price": result.target_price,
                "stop_loss": result.stop_loss,
                "reasoning": result.reasoning,
            }
        except Exception as exc:
            _analysis_cache[ticker] = {"status": "error", "ticker": ticker, "error": str(exc)}
        finally:
            _running.discard(ticker)

    background_tasks.add_task(_run)
    _analysis_cache[ticker] = {"status": "running", "ticker": ticker}
    return {"status": "started", "ticker": ticker}


@router.get("/deep/{ticker}")
async def get_deep_analysis(ticker: str) -> dict[str, Any]:
    """Poll for the result of a deep analysis."""
    if ticker not in _analysis_cache:
        return {"status": "not_started", "ticker": ticker}
    return _analysis_cache[ticker]


@router.post("/portfolio-score")
async def portfolio_score(payload: dict[str, Any]) -> dict[str, Any]:
    """Score the portfolio against the investor's profile targets."""
    cfg = load_config()
    profile = cfg.profile
    positions = payload.get("positions", [])

    total_value = sum(p.get("market_value", 0) for p in positions)
    total_pnl_pct = payload.get("total_pnl_pct", 0)

    # Check against targets
    on_target = total_pnl_pct >= profile.target_annual_return * 0.5  # halfway check
    at_risk = [
        p for p in positions
        if p.get("unrealized_pnl_pct", 0) < -profile.stop_loss_pct
    ]
    take_profit = [
        p for p in positions
        if p.get("unrealized_pnl_pct", 0) > profile.take_profit_pct
    ]

    return {
        "target_return": profile.target_annual_return,
        "current_return_pct": total_pnl_pct,
        "on_target": on_target,
        "risk_tolerance": profile.risk_tolerance,
        "stop_loss_alerts": [p["ticker"] for p in at_risk],
        "take_profit_alerts": [p["ticker"] for p in take_profit],
        "allocation_targets": profile.allocation.model_dump(),
        "recommendation": (
            f"Portfolio is {'on track' if on_target else 'below target'}. "
            f"{len(at_risk)} position(s) hit stop-loss threshold. "
            f"{len(take_profit)} position(s) hit take-profit threshold."
        ),
    }
