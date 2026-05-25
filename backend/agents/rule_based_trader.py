"""
Rule-based multi-analyst trading engine.
Five specialist analysts each score every stock independently,
then combine with mode-adjusted weights to produce a final decision.
Zero LLM calls — works entirely on technical + fundamental + sentiment data.
"""
from __future__ import annotations

import math
from typing import Any


# ── Analyst 1: Technical ──────────────────────────────────────────────────────

def technical_analyst(data: dict[str, Any]) -> tuple[float, str]:
    """
    Score -10 → +10 from RSI, MACD, Bollinger Bands, SMA crossovers.
    Positive = bullish signal, Negative = bearish.
    """
    score = 0.0
    lines: list[str] = []

    rsi       = float(data.get("rsi") or 50)
    macd_hist = float(data.get("macd_hist") or 0)
    bb_pct    = float(data.get("bb_pct") or 0.5)
    vs50      = float(data.get("price_vs_sma50") or 0)
    vs200     = float(data.get("price_vs_sma200") or 0)
    golden    = str(data.get("golden_cross") or "no").lower() == "yes"

    # ── RSI ───────────────────────────────────────────────────────────────────
    if rsi < 25:
        score += 4.0; lines.append(f"RSI {rsi:.1f} → extreme oversold, high reversal probability")
    elif rsi < 35:
        score += 2.5; lines.append(f"RSI {rsi:.1f} → oversold zone, buy signal")
    elif rsi < 45:
        score += 1.0; lines.append(f"RSI {rsi:.1f} → below neutral, mild bullish")
    elif rsi > 80:
        score -= 4.0; lines.append(f"RSI {rsi:.1f} → extreme overbought, high reversal risk")
    elif rsi > 70:
        score -= 2.5; lines.append(f"RSI {rsi:.1f} → overbought, consider selling")
    elif rsi > 60:
        score -= 0.8; lines.append(f"RSI {rsi:.1f} → approaching overbought")
    else:
        lines.append(f"RSI {rsi:.1f} → neutral zone")

    # ── MACD ─────────────────────────────────────────────────────────────────
    if macd_hist > 0.5:
        score += 2.5; lines.append(f"MACD histogram +{macd_hist:.3f} → strong bullish crossover")
    elif macd_hist > 0:
        score += 1.2; lines.append(f"MACD histogram +{macd_hist:.3f} → bullish momentum")
    elif macd_hist < -0.5:
        score -= 2.5; lines.append(f"MACD histogram {macd_hist:.3f} → strong bearish crossover")
    elif macd_hist < 0:
        score -= 1.2; lines.append(f"MACD histogram {macd_hist:.3f} → bearish momentum")

    # ── Bollinger Bands ───────────────────────────────────────────────────────
    if bb_pct < 0.1:
        score += 2.5; lines.append(f"BB% {bb_pct:.2f} → touching lower band (strong buy zone)")
    elif bb_pct < 0.25:
        score += 1.5; lines.append(f"BB% {bb_pct:.2f} → near lower band (buy zone)")
    elif bb_pct > 0.9:
        score -= 2.5; lines.append(f"BB% {bb_pct:.2f} → touching upper band (strong sell zone)")
    elif bb_pct > 0.75:
        score -= 1.5; lines.append(f"BB% {bb_pct:.2f} → near upper band (sell zone)")
    else:
        lines.append(f"BB% {bb_pct:.2f} → mid-band (neutral)")

    # ── SMA Trend ─────────────────────────────────────────────────────────────
    if vs50 > 5:
        score += 1.0; lines.append(f"{vs50:.1f}% above 50-SMA → strong uptrend")
    elif vs50 > 2:
        score += 0.5; lines.append(f"{vs50:.1f}% above 50-SMA → uptrend")
    elif vs50 < -5:
        score -= 1.0; lines.append(f"{vs50:.1f}% below 50-SMA → strong downtrend")
    elif vs50 < -2:
        score -= 0.5; lines.append(f"{vs50:.1f}% below 50-SMA → downtrend")

    # ── Golden / Death Cross ──────────────────────────────────────────────────
    if golden:
        score += 1.5; lines.append("Golden Cross: 50-SMA > 200-SMA → long-term uptrend confirmed")
    else:
        score -= 1.5; lines.append("Death Cross: 50-SMA < 200-SMA → long-term downtrend warning")

    return (min(max(score, -10), 10), " | ".join(lines))


# ── Analyst 2: Fundamental ────────────────────────────────────────────────────

def fundamental_analyst(data: dict[str, Any]) -> tuple[float, str]:
    """
    Score -10 → +10 from PE, PB, ROE, revenue growth, margins, analyst target.
    """
    score = 0.0
    lines: list[str] = []

    pe             = data.get("pe_ratio")
    pb             = data.get("price_to_book")
    roe            = data.get("roe")
    rev_growth     = data.get("revenue_growth")
    earn_growth    = data.get("earnings_growth")
    profit_margin  = data.get("profit_margin")
    debt_equity    = data.get("debt_to_equity")
    analyst_target = data.get("analyst_target")
    price          = float(data.get("price") or 0)

    # ── PE ratio ──────────────────────────────────────────────────────────────
    if pe and pe > 0:
        if pe < 12:
            score += 3.0; lines.append(f"PE {pe:.1f} → deeply undervalued")
        elif pe < 20:
            score += 1.5; lines.append(f"PE {pe:.1f} → fairly valued, attractive entry")
        elif pe < 30:
            score += 0.3; lines.append(f"PE {pe:.1f} → reasonable valuation")
        elif pe < 50:
            score -= 1.5; lines.append(f"PE {pe:.1f} → premium valuation, growth priced in")
        else:
            score -= 2.5; lines.append(f"PE {pe:.1f} → very expensive, high risk")

    # ── ROE ───────────────────────────────────────────────────────────────────
    if roe is not None:
        roe_pct = roe * 100
        if roe_pct > 25:
            score += 2.5; lines.append(f"ROE {roe_pct:.1f}% → exceptional business quality")
        elif roe_pct > 15:
            score += 1.5; lines.append(f"ROE {roe_pct:.1f}% → strong returns on equity")
        elif roe_pct > 8:
            score += 0.5; lines.append(f"ROE {roe_pct:.1f}% → adequate returns")
        elif roe_pct < 0:
            score -= 2.0; lines.append(f"ROE {roe_pct:.1f}% → destroying shareholder value")

    # ── Revenue growth ────────────────────────────────────────────────────────
    if rev_growth is not None:
        rg = rev_growth * 100
        if rg > 25:
            score += 2.0; lines.append(f"Revenue growth {rg:.1f}% → high-growth company")
        elif rg > 12:
            score += 1.0; lines.append(f"Revenue growth {rg:.1f}% → solid growth")
        elif rg < 0:
            score -= 1.5; lines.append(f"Revenue declining {rg:.1f}% → red flag")

    # ── Analyst target upside ─────────────────────────────────────────────────
    if analyst_target and price > 0:
        upside = (analyst_target - price) / price * 100
        if upside > 25:
            score += 2.0; lines.append(f"Analyst target ₹{analyst_target:.0f} → {upside:.0f}% upside potential")
        elif upside > 12:
            score += 1.0; lines.append(f"Analyst target implies {upside:.0f}% upside")
        elif upside < -15:
            score -= 1.5; lines.append(f"Analyst target implies {upside:.0f}% downside")

    # ── Profit margin ─────────────────────────────────────────────────────────
    if profit_margin is not None:
        pm = profit_margin * 100
        if pm > 20:
            score += 1.0; lines.append(f"Profit margin {pm:.1f}% → highly profitable")
        elif pm < 0:
            score -= 1.5; lines.append(f"Negative margin {pm:.1f}% → loss-making")

    if not lines:
        lines.append("Fundamental data unavailable — neutral score")

    return (min(max(score, -10), 10), " | ".join(lines))


# ── Analyst 3: Momentum ───────────────────────────────────────────────────────

def momentum_analyst(data: dict[str, Any]) -> tuple[float, str]:
    """
    Score -10 → +10 based on 52-week position and short-term price trend.
    """
    score = 0.0
    lines: list[str] = []

    price    = float(data.get("price") or 0)
    high_52w = data.get("52w_high")
    low_52w  = data.get("52w_low")
    vs50     = float(data.get("price_vs_sma50") or 0)
    vs200    = float(data.get("price_vs_sma200") or 0)

    if price > 0 and high_52w and low_52w:
        # Position in 52W range (0 = at low, 1 = at high)
        rng = high_52w - low_52w
        pos = (price - low_52w) / rng if rng > 0 else 0.5

        if pos < 0.20:
            score += 3.0; lines.append(f"Near 52W low (pos {pos*100:.0f}%) → potential reversal zone")
        elif pos < 0.35:
            score += 1.5; lines.append(f"In lower 52W range (pos {pos*100:.0f}%) → value zone")
        elif pos > 0.85:
            score -= 2.0; lines.append(f"Near 52W high (pos {pos*100:.0f}%) → breakout or exhaustion risk")
        elif pos > 0.70:
            score -= 0.8; lines.append(f"Upper 52W range (pos {pos*100:.0f}%) → elevated level")
        else:
            lines.append(f"Mid 52W range (pos {pos*100:.0f}%) → neutral momentum")

    # Short-term vs long-term momentum
    if vs50 > 0 and vs200 > 0:
        score += 1.5; lines.append(f"Above both 50 & 200-SMA → double momentum confirmation")
    elif vs50 < 0 and vs200 < 0:
        score -= 1.5; lines.append(f"Below both 50 & 200-SMA → no momentum support")
    elif vs50 > 0 and vs200 < 0:
        score += 0.5; lines.append(f"Short-term positive, long-term recovery forming")
    elif vs50 < 0 and vs200 > 0:
        score -= 0.5; lines.append(f"Short-term pullback in long-term uptrend")

    if not lines:
        lines.append("52W data unavailable — neutral momentum")

    return (min(max(score, -10), 10), " | ".join(lines))


# ── Analyst 4: Sentiment ──────────────────────────────────────────────────────

_BULLISH_WORDS = {
    "profit", "growth", "beat", "record", "strong", "positive", "upgrade",
    "buy", "outperform", "rally", "surge", "gain", "rise", "boost", "high",
    "dividend", "expansion", "robust", "turnaround", "recovery", "target",
    "acquisition", "deal", "order", "win", "contract", "launch", "approval",
}
_BEARISH_WORDS = {
    "loss", "decline", "miss", "weak", "negative", "downgrade", "sell",
    "underperform", "fall", "drop", "crash", "fraud", "debt", "default",
    "penalty", "probe", "investigation", "warning", "concern", "slowdown",
    "delay", "reject", "ban", "fine", "lawsuit", "layoff", "cut",
}


def sentiment_analyst(headlines: list[str], vix: float = 15.0) -> tuple[float, str]:
    """
    Score -10 → +10 from news keyword matching + VIX fear reading.
    """
    score = 0.0
    lines: list[str] = []

    bull = bear = 0
    for h in headlines:
        words = set(h.lower().split())
        bull += len(words & _BULLISH_WORDS)
        bear += len(words & _BEARISH_WORDS)

    if bull + bear > 0:
        net = bull - bear
        news_score = max(min(net * 0.7, 4.0), -4.0)
        score += news_score
        sentiment = "bullish" if net > 0 else "bearish" if net < 0 else "neutral"
        lines.append(f"News sentiment: {bull} bullish vs {bear} bearish signals → {sentiment}")
    else:
        lines.append("No relevant news found — neutral sentiment")

    # VIX fear/greed
    if vix < 12:
        score += 1.5; lines.append(f"VIX {vix:.1f} → extreme complacency, market very calm")
    elif vix < 16:
        score += 0.8; lines.append(f"VIX {vix:.1f} → low volatility, stable market")
    elif vix > 25:
        score -= 2.0; lines.append(f"VIX {vix:.1f} → high fear, elevated risk")
    elif vix > 20:
        score -= 1.0; lines.append(f"VIX {vix:.1f} → above-average volatility, cautious")
    else:
        lines.append(f"VIX {vix:.1f} → normal volatility range")

    return (min(max(score, -10), 10), " | ".join(lines))


# ── Analyst 5: Market Context ─────────────────────────────────────────────────

def market_analyst(nifty_pct: float, nifty_bank_pct: float, sector_pct: float | None) -> tuple[float, str]:
    """
    Score -10 → +10 based on broad market and sector direction.
    Rising market reduces risk; falling market adds caution.
    """
    score = 0.0
    lines: list[str] = []

    # NIFTY 50 direction
    if nifty_pct > 1.5:
        score += 2.5; lines.append(f"NIFTY +{nifty_pct:.2f}% → strong bull day, tailwind for all stocks")
    elif nifty_pct > 0.5:
        score += 1.2; lines.append(f"NIFTY +{nifty_pct:.2f}% → positive market breadth")
    elif nifty_pct > 0:
        score += 0.4; lines.append(f"NIFTY +{nifty_pct:.2f}% → mild positive")
    elif nifty_pct < -1.5:
        score -= 2.5; lines.append(f"NIFTY {nifty_pct:.2f}% → strong bear day, headwind for stocks")
    elif nifty_pct < -0.5:
        score -= 1.2; lines.append(f"NIFTY {nifty_pct:.2f}% → negative market sentiment")
    else:
        score -= 0.4; lines.append(f"NIFTY {nifty_pct:.2f}% → mild negative")

    # NIFTY Bank direction (financial sector health)
    if nifty_bank_pct > 1.0:
        score += 0.8; lines.append(f"NIFTY Bank +{nifty_bank_pct:.2f}% → financial sector strong")
    elif nifty_bank_pct < -1.0:
        score -= 0.8; lines.append(f"NIFTY Bank {nifty_bank_pct:.2f}% → financial sector weak")

    # Sector-specific
    if sector_pct is not None:
        if sector_pct > 1.5:
            score += 1.5; lines.append(f"Sector +{sector_pct:.2f}% → riding sector tailwind")
        elif sector_pct < -1.5:
            score -= 1.5; lines.append(f"Sector {sector_pct:.2f}% → sector headwind risk")

    return (min(max(score, -10), 10), " | ".join(lines))


# ── Combine all analysts → final decision ─────────────────────────────────────

def make_final_decision(
    ticker: str,
    tech: float, tech_reason: str,
    fund: float, fund_reason: str,
    mom:  float, mom_reason: str,
    sent: float, sent_reason: str,
    mkt:  float, mkt_reason: str,
    mode: str,
    price: float,
    stop_loss_pct: float = 0.08,
    take_profit_pct: float = 0.20,
) -> dict[str, Any]:
    """
    Weighted combination of all 5 analysts.
    Investor: fundamentals-heavy. Trader: technicals-heavy.
    """
    if mode == "trader":
        weights = {"technical": 0.40, "fundamental": 0.15, "momentum": 0.25, "sentiment": 0.12, "market": 0.08}
    else:
        weights = {"technical": 0.25, "fundamental": 0.40, "momentum": 0.15, "sentiment": 0.12, "market": 0.08}

    combined = (
        tech * weights["technical"]
        + fund * weights["fundamental"]
        + mom  * weights["momentum"]
        + sent * weights["sentiment"]
        + mkt  * weights["market"]
    )

    # Decision thresholds — calibrated for typical 5-analyst weighted score range.
    # ±1.5 = action signal, ±3.5 = strong conviction.
    if combined >= 3.5:
        action, signal = "BUY", "STRONG_BUY"
    elif combined >= 1.5:
        action, signal = "BUY", "BUY"
    elif combined <= -3.5:
        action, signal = "SELL", "STRONG_SELL"
    elif combined <= -1.5:
        action, signal = "SELL", "SELL"
    else:
        action, signal = "HOLD", "HOLD"

    # Trader mode: short on strong sell
    if mode == "trader" and action == "SELL":
        action = "SHORT"

    confidence = min(abs(combined) / 10.0, 0.95)

    # SHORT: stop is ABOVE entry (loss when price rises), target is BELOW entry
    if action == "SHORT":
        stop_loss   = round(price * (1 + stop_loss_pct), 2)
        take_profit = round(price * (1 - take_profit_pct), 2)
    else:
        stop_loss   = round(price * (1 - stop_loss_pct), 2)
        take_profit = round(price * (1 + take_profit_pct), 2)

    # Build detailed reasoning report
    reasoning = (
        f"**📊 Technical Analyst** (score {tech:+.1f}/10, weight {weights['technical']*100:.0f}%)\n"
        f"{tech_reason}\n\n"
        f"**📈 Fundamental Analyst** (score {fund:+.1f}/10, weight {weights['fundamental']*100:.0f}%)\n"
        f"{fund_reason}\n\n"
        f"**🚀 Momentum Analyst** (score {mom:+.1f}/10, weight {weights['momentum']*100:.0f}%)\n"
        f"{mom_reason}\n\n"
        f"**📰 Sentiment Analyst** (score {sent:+.1f}/10, weight {weights['sentiment']*100:.0f}%)\n"
        f"{sent_reason}\n\n"
        f"**🏦 Market Analyst** (score {mkt:+.1f}/10, weight {weights['market']*100:.0f}%)\n"
        f"{mkt_reason}\n\n"
        f"**🎯 Combined Score: {combined:+.2f}/10 → {signal}** (confidence {confidence*100:.0f}%)\n"
        f"Stop-loss: ₹{stop_loss} | Take-profit: ₹{take_profit}"
    )

    # One-line "why" — picks the two analysts whose weighted contribution to the
    # combined score is strongest IN THE DIRECTION OF the final action, so the
    # summary actually explains the trade.
    sign = 1 if combined >= 0 else -1
    contribs = [
        ("Technical",   tech * weights["technical"],   tech_reason),
        ("Fundamental", fund * weights["fundamental"], fund_reason),
        ("Momentum",    mom  * weights["momentum"],    mom_reason),
        ("Sentiment",   sent * weights["sentiment"],   sent_reason),
        ("Market",      mkt  * weights["market"],      mkt_reason),
    ]
    aligned = [(n, c, r) for (n, c, r) in contribs if c * sign > 0]
    aligned.sort(key=lambda x: abs(x[1]), reverse=True)
    top_two = aligned[:2] if aligned else sorted(contribs, key=lambda x: abs(x[1]), reverse=True)[:2]

    def _short(reason: str) -> str:
        # Take the first short phrase before a " | " or " → " marker
        head = reason.split("|", 1)[0].strip()
        head = head.split("→", 1)[0].strip() if "→" in head else head
        return head[:60].rstrip()

    why_summary = (
        f"{signal} · score {combined:+.1f}/10 · "
        + " + ".join(f"{n}: {_short(r)}" for (n, _, r) in top_two)
    )[:200]

    return {
        "ticker": ticker,
        "action": action,
        "signal": signal,
        "combined_score": round(combined, 2),
        "confidence": round(confidence, 2),
        "price_at_decision": price,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "reasoning": reasoning,
        "why_summary": why_summary,
        "key_technicals": tech_reason[:120],
        "key_fundamentals": fund_reason[:120],
        "risk_note": f"Stop-loss at {stop_loss_pct*100:.0f}% below entry. {'High VIX — reduce size.' if 'high fear' in sent_reason.lower() else 'Normal risk environment.'}",
        "scores": {
            "technical": round(tech, 2),
            "fundamental": round(fund, 2),
            "momentum": round(mom, 2),
            "sentiment": round(sent, 2),
            "market": round(mkt, 2),
        },
        "weights": weights,
    }
