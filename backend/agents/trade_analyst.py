"""
One Claude call per executed paper trade.
Generates a structured Bull Analyst vs Bear Analyst debate + Researcher synthesis.
Uses ALL technical indicators and fundamentals already gathered by the rule engine.
Stored permanently — shown in the Analysis tab.
"""
from __future__ import annotations

import json
from typing import Any

from backend.models.paper_trade import PaperTradeAnalysis, save_analysis
from backend.utils import cache as llm_cache


async def generate_trade_analysis(
    trade_id: str,
    portfolio_id: str,
    ticker: str,
    action: str,
    price: float,
    quantity: float,
    rule_signal: str,
    rule_score: float,
    stock_data: dict[str, Any],
    nifty_pct: float,
    vix: float,
    market_view: str,
) -> PaperTradeAnalysis | None:
    """
    Single Claude call per trade — bull/bear debate + researcher synthesis.
    Returns None if no API key or rate-limited (trade still executes fine).
    Cached 2h per ticker+signal so identical signals don't repeat the call.
    """
    from backend.models.config import load_config
    cfg = load_config()

    # Resolve key: config file → env var fallback
    import os as _os
    _env_map = {"anthropic": "ANTHROPIC_API_KEY", "google": "GOOGLE_API_KEY",
                "openai": "OPENAI_API_KEY", "deepseek": "DEEPSEEK_API_KEY"}
    api_key = cfg.llm_api_key or _os.environ.get(_env_map.get(cfg.llm_provider, ""), "")
    if not api_key:
        return None   # no key — skip analysis, trade still works
    cfg.llm_api_key = api_key

    # Cache key: same stock + same signal = same analysis
    cache_key = f"analysis:{ticker}:{rule_signal}:{round(rule_score, 1)}"
    cached = llm_cache.get(cache_key)

    if cached:
        # Build analysis from cache
        a = PaperTradeAnalysis(
            trade_id=trade_id,
            portfolio_id=portfolio_id,
            ticker=ticker,
            action=action,
            **cached,
        )
        save_analysis(a)
        return a

    # ── Build compact prompt (all technicals, no fluff) ───────────────────────
    s = stock_data
    rsi    = s.get("rsi", 50)
    macd_h = s.get("macd_hist", 0)
    bb     = s.get("bb_pct", 0.5)
    sma50  = s.get("price_vs_sma50", 0)
    sma200 = s.get("price_vs_sma200", 0)
    golden = s.get("golden_cross", "no")
    pe     = s.get("pe_ratio", "N/A")
    roe    = round((s.get("roe") or 0) * 100, 1)
    rev_g  = round((s.get("revenue_growth") or 0) * 100, 1)
    target = s.get("analyst_target", "N/A")
    hi52   = s.get("52w_high", "N/A")
    lo52   = s.get("52w_low", "N/A")
    news   = " | ".join((s.get("headlines") or [])[:3]) or "no recent news"

    rsi_label = "OVERSOLD" if rsi < 35 else "OVERBOUGHT" if rsi > 70 else "neutral"
    macd_label = "BULLISH" if macd_h > 0 else "BEARISH"
    bb_label = "lower-band(buy)" if bb < 0.25 else "upper-band(sell)" if bb > 0.75 else "mid-band"
    trend = "ABOVE both SMAs (uptrend)" if sma50 > 0 and sma200 > 0 else \
            "BELOW both SMAs (downtrend)" if sma50 < 0 and sma200 < 0 else "mixed"

    prompt = f"""Trade executed: {action} {quantity:.0f}× {ticker} @ ₹{price:.2f}
Rule engine: {rule_signal} (score {rule_score:+.2f}/10)
Market: NIFTY {nifty_pct:+.2f}% | VIX {vix:.1f} | {market_view[:80]}

TECHNICALS:
  RSI={rsi:.1f} ({rsi_label}) | MACD_HIST={macd_h:.3f} ({macd_label}) | BB%={bb:.2f} ({bb_label})
  vs50SMA={sma50:+.1f}% | vs200SMA={sma200:+.1f}% | {trend} | GoldenCross={golden}

FUNDAMENTALS:
  PE={pe} | ROE={roe}% | RevenueGrowth={rev_g}% | AnalystTarget=₹{target}
  52W: Low=₹{lo52} High=₹{hi52}

NEWS: {news}

Respond ONLY with this JSON (no markdown, no extra text):
{{
  "bull": {{
    "thesis": "<2 sentences: strongest case for {action} this stock citing specific numbers>",
    "catalysts": ["<catalyst1>", "<catalyst2>"],
    "target": <price number>,
    "confidence": "high|medium|low"
  }},
  "bear": {{
    "thesis": "<2 sentences: strongest case AGAINST {action} with specific data points>",
    "risks": ["<risk1>", "<risk2>"],
    "stop": <price number>,
    "confidence": "high|medium|low"
  }},
  "researcher": {{
    "verdict": "{action}|HOLD",
    "reasoning": "<2 sentences: who wins the debate and why>",
    "conviction": "high|medium|low",
    "key_factor": "<single most decisive indicator or data point>"
  }}
}}"""

    try:
        import httpx

        if cfg.llm_provider == "google":
            model = cfg.llm_model or "gemini-2.0-flash-lite"
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={cfg.llm_api_key}"
            body = {
                "contents": [{"parts": [{"text": "You are a concise stock market analyst. " + prompt}]}],
                "generationConfig": {"maxOutputTokens": 400, "temperature": 0.2},
            }
            async with httpx.AsyncClient(timeout=12) as client:
                r = await client.post(url, json=body)
            if r.status_code != 200:
                return None
            raw = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()

        elif cfg.llm_provider == "anthropic":
            async with httpx.AsyncClient(timeout=12) as client:
                r = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={"x-api-key": cfg.llm_api_key, "anthropic-version": "2023-06-01"},
                    json={
                        "model": cfg.llm_model or "claude-haiku-4-5-20251001",
                        "max_tokens": 400,
                        "system": "You are a concise stock market analyst. Always respond with valid JSON only.",
                        "messages": [{"role": "user", "content": prompt}],
                    },
                )
            if r.status_code != 200:
                return None
            raw = r.json()["content"][0]["text"].strip()

        elif cfg.llm_provider == "openai":
            async with httpx.AsyncClient(timeout=12) as client:
                r = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {cfg.llm_api_key}"},
                    json={
                        "model": cfg.llm_model or "gpt-4o-mini",
                        "max_tokens": 400,
                        "temperature": 0.2,
                        "messages": [
                            {"role": "system", "content": "You are a concise stock market analyst. Respond with valid JSON only."},
                            {"role": "user", "content": prompt},
                        ],
                    },
                )
            if r.status_code != 200:
                return None
            raw = r.json()["choices"][0]["message"]["content"].strip()

        else:
            return None

        # Clean JSON (strip markdown fences if present)
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        d = json.loads(raw)
        bull = d.get("bull", {})
        bear = d.get("bear", {})
        res  = d.get("researcher", {})

        fields = {
            "bull_thesis":            bull.get("thesis", ""),
            "bull_catalysts":         json.dumps(bull.get("catalysts", [])),
            "bull_target":            float(bull.get("target") or 0),
            "bull_confidence":        bull.get("confidence", "medium"),
            "bear_thesis":            bear.get("thesis", ""),
            "bear_risks":             json.dumps(bear.get("risks", [])),
            "bear_stop":              float(bear.get("stop") or 0),
            "bear_confidence":        bear.get("confidence", "medium"),
            "researcher_verdict":     res.get("verdict", action),
            "researcher_reasoning":   res.get("reasoning", ""),
            "researcher_conviction":  res.get("conviction", "medium"),
            "researcher_key_factor":  res.get("key_factor", ""),
            "tech_summary": (
                f"RSI={rsi:.1f}({rsi_label}) MACD={macd_h:.3f}({macd_label}) "
                f"BB%={bb:.2f}({bb_label}) vs50SMA={sma50:+.1f}% Golden={golden} "
                f"PE={pe} ROE={roe}% Target=₹{target}"
            ),
        }

        # Cache for 2 hours
        llm_cache.set(cache_key, fields, ttl_seconds=7200)

        a = PaperTradeAnalysis(
            trade_id=trade_id,
            portfolio_id=portfolio_id,
            ticker=ticker,
            action=action,
            **fields,
        )
        save_analysis(a)
        return a

    except Exception:
        return None   # analysis failure never blocks the trade
