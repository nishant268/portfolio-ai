from __future__ import annotations

import json
import re
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.models.chat import (
    add_message, create_session, delete_message, delete_session,
    get_messages, get_session_by_id, list_sessions,
)
from backend.models.config import load_config
from backend.scrapers.news import fetch_all_news
from backend.scrapers.nse import nse

router = APIRouter(prefix="/api/chat", tags=["chat"])

# ── REST CRUD ─────────────────────────────────────────────────────────────────

@router.get("/sessions")
async def all_sessions():
    return {"sessions": [s.model_dump() for s in list_sessions()]}


@router.post("/sessions")
async def new_session(payload: dict[str, str] = {}):
    sess = create_session(
        title=payload.get("title", "New Chat"),
        mode=payload.get("mode", "investor"),
    )
    return sess.model_dump()


@router.delete("/sessions/{sid}")
async def del_session(sid: str):
    if not delete_session(sid):
        raise HTTPException(404, "Session not found")
    return {"ok": True}


@router.get("/sessions/{sid}/messages")
async def get_msgs(sid: str):
    sess = get_session_by_id(sid)
    if not sess:
        raise HTTPException(404, "Session not found")
    msgs = get_messages(sid)
    return {
        "session": sess.model_dump(),
        "messages": [
            {**m.model_dump(), "sources": json.loads(m.sources_json)}
            for m in msgs
        ],
    }


@router.delete("/sessions/{sid}/messages/{mid}")
async def del_msg(sid: str, mid: str):
    if not delete_message(mid):
        raise HTTPException(404, "Message not found")
    return {"ok": True}


# ── AI Q&A ────────────────────────────────────────────────────────────────────

class AskPayload(BaseModel):
    question: str
    mode: str = "investor"


_KEY_ENV: dict[str, str] = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "google": "GOOGLE_API_KEY",
    "azure": "AZURE_OPENAI_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "xai": "XAI_API_KEY",
    "ollama": "",   # local — no key needed
}


def _check_llm_key(provider: str, stored_key: str = "") -> str | None:
    """Return None if key is available (config or env var), else a clear error."""
    import os
    # Ollama is local — no key needed
    if provider == "ollama":
        return None
    # Key stored in config file (entered via Setup UI) — best path
    if stored_key:
        return None
    # Fall back to environment variable
    env_var = _KEY_ENV.get(provider, "")
    if env_var and os.environ.get(env_var):
        return None
    # No key found anywhere — guide the user
    env_hint = f"`{env_var}`" if env_var else "the provider API key"
    return (
        f"🔑 **No API key configured for {provider}.**\n\n"
        f"Go to **Setup → Step 3 (AI Model)** and paste your API key in the key field — "
        f"it will be saved securely in your local config.\n\n"
        f"**Supported providers and where to get keys:**\n"
        f"- **OpenAI** → platform.openai.com/api-keys\n"
        f"- **Anthropic** → console.anthropic.com/keys\n"
        f"- **Google Gemini** → aistudio.google.com/apikey\n"
        f"- **Ollama** → free, runs locally (install from ollama.ai)\n\n"
        f"Or switch to **Ollama** in Setup for a fully free, local option."
    )


@router.post("/sessions/{sid}/ask")
async def ask(sid: str, payload: AskPayload):
    sess = get_session_by_id(sid)
    if not sess:
        raise HTTPException(404, "Session not found")

    cfg = load_config()
    question = payload.question.strip()
    mode = payload.mode

    # Save user message first (always persisted)
    add_message(sid, "user", question)

    # ── Pre-flight: check API key is configured ────────────────────────────────
    key_error = _check_llm_key(cfg.llm_provider, cfg.llm_api_key)
    if key_error:
        add_message(sid, "assistant", key_error)
        return {"answer": key_error, "sources": {}}

    # ── Cache check — same question in same mode = no API call ────────────────
    from backend.utils import cache as llm_cache
    cache_key = f"chat:{mode}:{question.lower().strip()}"
    cached_answer = llm_cache.get(cache_key)
    if cached_answer:
        add_message(sid, "assistant", cached_answer + "\n\n*(cached response — no API call used)*")
        return {"answer": cached_answer, "sources": {"cached": True}}

    # Build context
    context = await _build_context(question, mode, cfg)

    # Get conversation history — only last 4 exchanges to save tokens
    all_msgs = get_messages(sid)[:-1]
    history = [
        {"role": m.role, "content": m.content[:400]}   # truncate long messages
        for m in all_msgs[-8:]                          # last 4 exchanges = 8 messages
    ]

    # Generate AI response — catch all errors and persist them as assistant messages
    try:
        answer = await _generate_answer(question, mode, context, history, cfg)
    except Exception as exc:
        err_str = str(exc)
        # ── Friendly error messages for common failures ────────────────────────
        if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "quota" in err_str.lower():
            err_text = (
                "⏳ **Rate limit / Quota exhausted** on your AI provider.\n\n"
                "**How to fix:**\n"
                "- **Wait ~1 minute** then ask again (per-minute quota resets)\n"
                "- **Or wait until tomorrow** if daily quota is exhausted (free tier: 1500 req/day)\n"
                "- **Or enable billing** on your Google AI Studio account for higher limits\n"
                "- **Or switch provider** in Setup → Step 3 → use OpenAI / Anthropic / Ollama\n\n"
                f"*Retry after: {_extract_retry_delay(err_str)} seconds*"
            )
        elif "401" in err_str or "authentication" in err_str.lower() or "api_key" in err_str.lower():
            err_text = (
                "🔑 **Invalid API key.** Go to **Setup → Step 3** and re-enter your API key."
            )
        elif "404" in err_str or "NOT_FOUND" in err_str:
            err_text = (
                f"❌ **Model not found.** The model `{cfg.llm_model}` may be unavailable.\n\n"
                "Go to **Setup → Step 3** and select a different model."
            )
        else:
            err_text = (
                f"⚠️ AI error: {err_str[:200]}\n\n"
                f"Check your **{cfg.llm_provider}** API key in Setup → Step 3."
            )
        add_message(sid, "assistant", err_text)
        return {"answer": err_text, "sources": {}}

    # Cache the answer (30 min TTL) — duplicate questions won't hit the API
    llm_cache.set(cache_key, answer, ttl_seconds=1800)

    # Save assistant message
    add_message(sid, "assistant", answer, context.get("_meta", {}))

    return {
        "answer": answer,
        "sources": context.get("_meta", {}),
    }


def _extract_retry_delay(err_str: str) -> str:
    """Pull the retry delay seconds out of a 429 error message."""
    import re
    m = re.search(r"retry[^\d]*(\d+(?:\.\d+)?)\s*s", err_str, re.I)
    return m.group(1) if m else "30–60"


# ── Context builder ───────────────────────────────────────────────────────────

_SKIP_WORDS = {
    "WHAT", "WHEN", "HOW", "WHY", "WHO", "IS", "ARE", "THE", "AND", "OR",
    "FOR", "NSE", "BSE", "FNO", "IPO", "SIP", "MF", "ETF", "PE", "RSI",
    "CMP", "BUY", "SELL", "HOLD", "PUT", "CALL", "ATM", "ITM", "OTM",
    "PCR", "OI", "LTP", "IV", "MACD", "VWAP", "EMA", "SMA",
}


async def _build_context(question: str, mode: str, cfg: Any) -> dict[str, Any]:
    from portfolio_ai.data.market_data import compute_technicals, get_fundamentals, get_news_headlines

    ctx: dict[str, Any] = {}
    meta: dict[str, Any] = {"fetched": []}

    # ── Market indices ──
    try:
        indices = await nse.all_indices()
        key = [i for i in indices if i.get("indexSymbol") in
               ["NIFTY 50", "NIFTY BANK", "NIFTY IT", "INDIA VIX", "NIFTY MIDCAP 100"]]
        ctx["indices"] = key
        meta["fetched"].append("market_indices")
    except Exception:
        pass

    # ── News ──
    try:
        news = await fetch_all_news()
        ctx["news"] = [f"{n['source']}: {n['title']}" for n in news[:12]]
        meta["fetched"].append("news")
    except Exception:
        pass

    # ── Extract tickers from question ──
    words = re.findall(r'\b[A-Z]{2,12}\b', question.upper())
    tickers = [w for w in words if w not in _SKIP_WORDS][:4]
    ctx["tickers_detected"] = tickers

    for ticker in tickers:
        try:
            tech = compute_technicals(ticker)
            fund = get_fundamentals(ticker)
            ctx[f"stock_{ticker}"] = {
                "technicals": {k: v for k, v in tech.items() if not isinstance(v, float) or abs(v) < 1e9},
                "fundamentals": {k: v for k, v in fund.items() if v is not None},
            }
            meta["fetched"].append(f"stock_data:{ticker}")
        except Exception:
            pass

    # ── F&O context for trader mode ──
    if mode == "trader":
        from backend.scrapers.nse_fo import option_chain, fii_dii_data
        fo_symbols = [t for t in (tickers or ["NIFTY"]) if t in
                      {"NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"} or len(t) >= 3]
        for sym in fo_symbols[:2]:
            try:
                chain = await option_chain(sym)
                if "error" not in chain:
                    ctx[f"options_{sym}"] = {
                        "underlying": chain["underlying"],
                        "pcr": chain["pcr"],
                        "max_pain": chain["max_pain"],
                        "total_ce_oi": chain["total_ce_oi"],
                        "total_pe_oi": chain["total_pe_oi"],
                    }
                    meta["fetched"].append(f"options_chain:{sym}")
            except Exception:
                pass
        try:
            fii = await fii_dii_data()
            if fii:
                ctx["fii_dii"] = fii
                meta["fetched"].append("fii_dii")
        except Exception:
            pass

    # ── Portfolio (if configured) ──
    try:
        if cfg.zerodha.access_token and cfg.configured:
            from kiteconnect import KiteConnect
            kite = KiteConnect(api_key=cfg.zerodha.api_key)
            kite.set_access_token(cfg.zerodha.access_token)
            holdings = kite.holdings()
            ctx["portfolio"] = [
                {
                    "ticker": h["tradingsymbol"],
                    "qty": h["quantity"],
                    "avg_cost": h["average_price"],
                    "ltp": h["last_price"],
                    "pnl_pct": round((h["last_price"] - h["average_price"]) / h["average_price"] * 100, 2)
                    if h["average_price"] else 0,
                }
                for h in holdings if h["quantity"] > 0
            ]
            meta["fetched"].append("portfolio")
    except Exception:
        pass

    ctx["_meta"] = meta
    return ctx


# ── LLM response ──────────────────────────────────────────────────────────────

async def _generate_answer(
    question: str,
    mode: str,
    context: dict[str, Any],
    history: list[dict[str, str]],
    cfg: Any,
) -> str:
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

    mode_desc = (
        "an active trader focused on technical analysis, F&O strategies, intraday/swing trades, "
        "options Greeks (Delta, Gamma, Theta, Vega), PCR analysis, and momentum"
        if mode == "trader"
        else
        "a long-term investor focused on fundamentals, portfolio allocation, CAGR, SIP strategies, "
        "business quality, moats, and margin of safety"
    )

    indices_str = "\n".join(
        f"  {i.get('indexSymbol')}: {i.get('last')} ({'+' if (i.get('percentChange') or 0) >= 0 else ''}{i.get('percentChange')}%)"
        for i in context.get("indices", [])
    )
    news_str = "\n".join(f"  • {n}" for n in context.get("news", [])[:5])   # limit news to save tokens

    stock_sections = ""
    for key, val in context.items():
        if key.startswith("stock_"):
            ticker = key[6:]
            t = val.get("technicals", {})
            f = val.get("fundamentals", {})
            stock_sections += f"""
{ticker}:
  RSI(14)={t.get('rsi_14')} | MACD={t.get('macd')} | Signal={t.get('macd_signal')}
  vs 50SMA={t.get('price_vs_sma50')}% | Golden Cross={t.get('golden_cross')}
  PE={f.get('pe_ratio')} | PB={f.get('price_to_book')} | ROE={f.get('roe')}
  52W High={f.get('52w_high')} | Low={f.get('52w_low')} | Analyst Target={f.get('analyst_target')}
"""

    fo_sections = ""
    for key, val in context.items():
        if key.startswith("options_"):
            sym = key[8:]
            fo_sections += f"""
{sym} Options:
  Underlying={val.get('underlying')} | PCR={val.get('pcr')} | Max Pain={val.get('max_pain')}
  Total CE OI={val.get('total_ce_oi'):,} | Total PE OI={val.get('total_pe_oi'):,}
"""

    portfolio_str = ""
    if context.get("portfolio"):
        portfolio_str = "My Portfolio:\n" + "\n".join(
            f"  {p['ticker']}: {p['qty']} units @ ₹{p['avg_cost']} → {p['pnl_pct']:+.1f}%"
            for p in context["portfolio"]
        )

    # Compact system prompt — fewer tokens, same quality
    system_prompt = (
        f"You are a concise Indian stock market AI ({mode_desc}). "
        f"Market: {indices_str.strip() or 'data unavailable'}. "
        f"News: {' | '.join(context.get('news', [])[:3])}. "
        f"{stock_sections.strip()} {fo_sections.strip()} {portfolio_str.strip()} "
        f"Answer in 3-5 sentences. Use ₹. Bold key terms. State risks. Don't fabricate data."
    )

    from portfolio_ai.agents.portfolio_evaluator import _make_llm
    # Default to haiku for chat — cheapest, fast enough
    model = cfg.llm_model or (
        "claude-haiku-4-5-20251001" if cfg.llm_provider == "anthropic"
        else "gpt-4o-mini" if cfg.llm_provider == "openai"
        else cfg.llm_model
    )
    llm = _make_llm(cfg.llm_provider, model, temperature=0.2, api_key=cfg.llm_api_key or None)

    messages: list[Any] = [SystemMessage(content=system_prompt)]
    for h in history:   # already capped at 8 messages above
        if h["role"] == "user":
            messages.append(HumanMessage(content=h["content"]))
        else:
            messages.append(AIMessage(content=h["content"]))
    messages.append(HumanMessage(content=question))

    resp = await llm.ainvoke(messages)
    return resp.content
