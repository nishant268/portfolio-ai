"""
TradingAgents-style streaming analysis pipeline.
Each agent produces rich, descriptive first-person reasoning with specific data citations.
Pipeline mirrors TradingAgents: Analyst Team → Research Team → Trader → Risk Mgmt → Portfolio Mgmt
LLM: ONE call per pipeline for Research Team + Portfolio Manager report.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any, AsyncGenerator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/api/agent-stream", tags=["agent-stream"])

PIPELINE = [
    ("Analyst Team",    "Technical Analyst",    "rule"),
    ("Analyst Team",    "Fundamental Analyst",  "rule"),
    ("Analyst Team",    "Momentum Analyst",     "rule"),
    ("Analyst Team",    "Sentiment Analyst",    "rule"),
    ("Analyst Team",    "Market Analyst",       "rule"),
    ("Research Team",   "Bull Researcher",      "llm"),
    ("Research Team",   "Bear Researcher",      "llm"),
    ("Research Team",   "Research Manager",     "llm"),
    ("Trading Team",    "Trader",               "rule"),
    ("Risk Management", "Risky Analyst",        "rule"),
    ("Risk Management", "Neutral Analyst",      "rule"),
    ("Risk Management", "Safe Analyst",         "rule"),
    ("Portfolio Mgmt",  "Portfolio Manager",    "decision"),
]


def _t() -> str:
    return datetime.now().strftime("%H:%M:%S")


def _sse(d: dict[str, Any]) -> str:
    return f"data: {json.dumps(d)}\n\n"


# ── Narrative generators (rule-based, no LLM) ─────────────────────────────────

def _tech_narrative(ticker: str, price: float, d: dict, score: float) -> list[str]:
    rsi = float(d.get("rsi", 50) or 50)
    macd_h = float(d.get("macd_hist", 0) or 0)
    bb = float(d.get("bb_pct", 0.5) or 0.5)
    sma50 = float(d.get("price_vs_sma50", 0) or 0)
    sma200 = float(d.get("price_vs_sma200", 0) or 0)
    golden = str(d.get("golden_cross", "no")).lower() == "yes"
    msgs = []

    # RSI
    if rsi < 30:
        msgs.append(f"Technical Analyst: RSI has plunged to {rsi:.1f} — extreme oversold territory. Historically on NSE, RSI readings below 30 precede 70%+ probability mean-reversion bounces. This is one of the strongest short-term buy signals in technical analysis.")
    elif rsi < 40:
        msgs.append(f"Technical Analyst: RSI at {rsi:.1f} is firmly in the oversold zone. Sellers have overextended, and at this level institutional accumulation typically begins. The exhaustion of selling momentum is a classic setup for reversal.")
    elif rsi > 75:
        msgs.append(f"Technical Analyst: RSI at {rsi:.1f} is dangerously overbought — buyer fatigue is setting in. At this extreme, even positive news catalysts struggle to push prices higher. I'm seeing the same pattern that preceded several NSE corrections in recent years.")
    elif rsi > 65:
        msgs.append(f"Technical Analyst: RSI at {rsi:.1f} is elevated, approaching overbought territory. Upside momentum is intact, but the risk/reward for fresh longs is deteriorating. Existing positions should tighten stop-losses.")
    else:
        msgs.append(f"Technical Analyst: RSI at {rsi:.1f} sits in neutral territory. There is no extreme signal here — the stock is in equilibrium between buyers and sellers. I'll weight other indicators more heavily in my assessment.")

    # MACD
    if macd_h > 0.5:
        msgs.append(f"Technical Analyst: MACD histogram is strongly positive at {macd_h:.3f}, confirming accelerating bullish momentum. This level of histogram divergence typically signals that institutional money is actively accumulating. The crossover is fresh and gaining strength.")
    elif macd_h > 0:
        msgs.append(f"Technical Analyst: MACD histogram just turned positive at {macd_h:.3f} — a fresh bullish crossover. The signal is early, which means maximum upside potential with defined downside. This is the type of setup momentum traders look for.")
    elif macd_h < -0.5:
        msgs.append(f"Technical Analyst: MACD histogram at {macd_h:.3f} reflects deep and accelerating bearish momentum. This magnitude suggests institutional distribution, not mere retail profit-booking. The trend here is well-established and concerning.")
    else:
        msgs.append(f"Technical Analyst: MACD histogram at {macd_h:.3f} shows mild bearish momentum. The signal isn't strong enough to act on alone, but it reinforces caution and suggests waiting for a clearer entry.")

    # Bollinger Bands
    if bb < 0.15:
        msgs.append(f"Technical Analyst: Price is at the extreme lower Bollinger Band (BB%B={bb:.2f}). This is a mean-reversion buy signal — 85% of price action occurs within the bands, and being at the lower extreme suggests a statistical snap-back is overdue.")
    elif bb > 0.85:
        msgs.append(f"Technical Analyst: Price is pressing against the upper Bollinger Band (BB%B={bb:.2f}). While strong trends can 'walk the band,' this level historically marks areas where risk/reward tilts toward sellers in NSE large-caps.")

    # SMA trend
    if sma50 > 0 and sma200 > 0:
        trend_str = "The Golden Cross is in effect, confirming a long-term bullish structure." if golden else "Both SMAs are rising, suggesting a healthy uptrend."
        msgs.append(f"Technical Analyst: Price is trading {sma50:+.1f}% above the 50-day SMA and {sma200:+.1f}% above the 200-day SMA. {trend_str} This dual-SMA confirmation is one of the most reliable trend filters available.")
    elif sma50 < 0 and sma200 < 0:
        msgs.append(f"Technical Analyst: Price is below both the 50-day ({sma50:+.1f}%) and 200-day ({sma200:+.1f}%) SMAs — a 'double-below' pattern that signals sustained structural weakness. Without reclaiming these levels, any rally should be treated as a short-covering bounce.")

    # Verdict
    if score > 4:
        msgs.append(f"Technical Analyst: My overall technical score is {score:+.1f}/10 → STRONG BUY. The confluence of oversold indicators, fresh MACD crossover, and Bollinger Band positioning at ₹{price:.2f} represents a high-conviction technical entry.")
    elif score > 2:
        msgs.append(f"Technical Analyst: Overall technical score {score:+.1f}/10 → BUY. Multiple indicators are supportive. I recommend accumulation on any intraday dips.")
    elif score < -4:
        msgs.append(f"Technical Analyst: Overall technical score {score:+.1f}/10 → STRONG SELL. The weight of evidence across RSI, MACD, and moving averages is decisively bearish at ₹{price:.2f}.")
    elif score < -2:
        msgs.append(f"Technical Analyst: Overall technical score {score:+.1f}/10 → SELL. Technical deterioration is broad-based. I'd reduce exposure until signals improve.")
    else:
        msgs.append(f"Technical Analyst: Technical score {score:+.1f}/10 → HOLD. No compelling directional signal at ₹{price:.2f}. Waiting for cleaner setup.")

    return msgs


def _fund_narrative(ticker: str, price: float, d: dict, score: float) -> list[str]:
    pe = d.get("pe_ratio")
    roe = d.get("roe")
    rev_g = d.get("revenue_growth")
    tgt = d.get("analyst_target")
    hi52 = d.get("52w_high")
    lo52 = d.get("52w_low")
    margin = d.get("profit_margin")
    msgs = []

    # PE valuation
    if pe:
        if float(pe) < 15:
            msgs.append(f"Fundamental Analyst: At a PE of {pe:.1f}x, {ticker} is trading well below the NSE large-cap average of ~22x. This is a meaningful discount that provides a margin of safety. For a quality business, this kind of undervaluation rarely persists.")
        elif float(pe) < 25:
            msgs.append(f"Fundamental Analyst: PE of {pe:.1f}x is within fair-value range for an NSE large-cap. The stock is neither screaming cheap nor expensive. Valuation alone doesn't make the case — I'll lean heavily on growth quality.")
        elif float(pe) < 40:
            msgs.append(f"Fundamental Analyst: PE at {pe:.1f}x represents a premium valuation that needs to be justified by superior growth. At this multiple, investors are already pricing in significant future earnings expansion — execution risk is elevated.")
        else:
            msgs.append(f"Fundamental Analyst: PE of {pe:.1f}x is extremely elevated. At this valuation, any earnings disappointment — even a 5-10% miss — could trigger a 20-30% de-rating. I'm deeply uncomfortable recommending fresh longs at this multiple.")

    # ROE quality
    if roe is not None:
        roe_pct = float(roe) * 100
        if roe_pct > 20:
            msgs.append(f"Fundamental Analyst: ROE of {roe_pct:.1f}% is exceptional — this business consistently generates returns well above the cost of capital. Companies sustaining ROE>20% for multiple years tend to compound shareholder wealth effectively.")
        elif roe_pct > 12:
            msgs.append(f"Fundamental Analyst: ROE of {roe_pct:.1f}% is solid, indicating efficient use of shareholder capital. This is the kind of fundamental quality that attracts long-term institutional flows.")
        elif roe_pct > 0:
            msgs.append(f"Fundamental Analyst: ROE at {roe_pct:.1f}% is below average. While not alarming, it suggests the business isn't generating the capital efficiency I'd want to see at this valuation.")
        else:
            msgs.append(f"Fundamental Analyst: Negative ROE of {roe_pct:.1f}% is a serious red flag — the business is currently destroying shareholder capital. Until this reverses, I cannot recommend this as an investment.")

    # Growth
    if rev_g is not None:
        rg_pct = float(rev_g) * 100
        if rg_pct > 20:
            msgs.append(f"Fundamental Analyst: Revenue growing at {rg_pct:.1f}% is impressive — this pace significantly outpaces NSE benchmark growth. High-growth companies at reasonable multiples tend to be the best long-term compounders.")
        elif rg_pct > 8:
            msgs.append(f"Fundamental Analyst: Revenue growth of {rg_pct:.1f}% is healthy, tracking above nominal GDP growth. This confirms the business has pricing power and is gaining market share.")
        elif rg_pct < 0:
            msgs.append(f"Fundamental Analyst: Revenue is declining at {rg_pct:.1f}% — this is a fundamental concern that no amount of operational efficiency can fully offset. Top-line growth is the foundation of long-term value creation.")

    # Analyst consensus target
    if tgt and price > 0:
        upside = (float(tgt) - price) / price * 100
        if upside > 20:
            msgs.append(f"Fundamental Analyst: Consensus analyst target of ₹{float(tgt):.0f} implies {upside:.0f}% upside from current ₹{price:.2f}. This level of institutional consensus upside is a strong contrarian signal and suggests the stock is significantly mispriced.")
        elif upside > 8:
            msgs.append(f"Fundamental Analyst: Analyst target ₹{float(tgt):.0f} implies {upside:.0f}% upside. Moderate consensus upside — the street sees value but no urgent catalyst.")
        elif upside < -10:
            msgs.append(f"Fundamental Analyst: Analyst consensus target ₹{float(tgt):.0f} is {abs(upside):.0f}% BELOW current price. This is bearish — the collective view of sell-side analysts is that the stock is overvalued.")

    if score > 3:
        msgs.append(f"Fundamental Analyst: Fundamental score {score:+.1f}/10 → Strong buy from a value perspective. The combination of reasonable valuation and quality fundamentals makes ₹{price:.2f} an attractive entry.")
    elif score < -3:
        msgs.append(f"Fundamental Analyst: Fundamental score {score:+.1f}/10 → Fundamentally challenged. I would not initiate or add at these levels.")
    else:
        msgs.append(f"Fundamental Analyst: Fundamental score {score:+.1f}/10 → Neutral. No compelling fundamental catalyst in either direction right now.")

    return msgs


def _mom_narrative(ticker: str, price: float, d: dict, score: float) -> list[str]:
    sma50 = float(d.get("price_vs_sma50", 0) or 0)
    sma200 = float(d.get("price_vs_sma200", 0) or 0)
    hi52 = d.get("52w_high")
    lo52 = d.get("52w_low")
    msgs = []

    if hi52 and lo52 and price > 0:
        rng = float(hi52) - float(lo52)
        pos = ((price - float(lo52)) / rng * 100) if rng > 0 else 50
        if pos < 20:
            msgs.append(f"Momentum Analyst: {ticker} is trading near its 52-week low, at only the {pos:.0f}th percentile of its annual range (Low ₹{float(lo52):.0f}, High ₹{float(hi52):.0f}). While this signals recent weakness, it's precisely these depressed levels where long-term investors find asymmetric opportunities — maximum fear, maximum potential reward.")
        elif pos < 35:
            msgs.append(f"Momentum Analyst: At {pos:.0f}% of its 52-week range (₹{float(lo52):.0f}–₹{float(hi52):.0f}), {ticker} is in the lower value zone. Momentum is negative, but the stock hasn't broken down to new lows — a stabilization pattern worth monitoring.")
        elif pos > 80:
            msgs.append(f"Momentum Analyst: {ticker} is trading at {pos:.0f}% of its 52-week range, near its annual high of ₹{float(hi52):.0f}. This is a double-edged sword — breakout momentum is powerful, but chasing highs significantly reduces margin of safety.")
        else:
            msgs.append(f"Momentum Analyst: At {pos:.0f}% of the 52-week range (₹{float(lo52):.0f}–₹{float(hi52):.0f}), {ticker} is in the middle of its annual range. No strong momentum signal in either direction.")

    if sma50 > 3 and sma200 > 0:
        msgs.append(f"Momentum Analyst: The dual confirmation of trading above both the 50-SMA (+{sma50:.1f}%) and 200-SMA (+{sma200:.1f}%) is the gold standard for trend traders. Momentum is constructive — the path of least resistance remains upward.")
    elif sma50 < -3 and sma200 < 0:
        msgs.append(f"Momentum Analyst: Trading below both the 50-SMA ({sma50:.1f}%) and 200-SMA ({sma200:.1f}%) confirms a broken trend structure. Momentum traders would categorize this as a 'no fly zone' — avoid new longs until moving averages are reclaimed.")

    msgs.append(f"Momentum Analyst: Momentum score {score:+.1f}/10. {'The trend is your friend at these levels — momentum supports entry.' if score > 2 else 'Against-trend positioning is risky here — wait for momentum to stabilize.' if score < -2 else 'Momentum is neutral; other factors will drive this decision.'}")
    return msgs


def _sent_narrative(ticker: str, headlines: list, vix: float, score: float) -> list[str]:
    msgs = []
    pos_words = ["profit", "growth", "beat", "record", "strong", "upgrade", "rally", "gain"]
    neg_words = ["loss", "decline", "miss", "weak", "probe", "fraud", "fall", "penalty"]
    bull_count = sum(1 for h in headlines for w in pos_words if w in h.lower())
    bear_count = sum(1 for h in headlines for w in neg_words if w in h.lower())

    if headlines:
        if bull_count > bear_count:
            msgs.append(f"Sentiment Analyst: Scanning {len(headlines)} recent headlines for {ticker}, I'm finding predominantly positive sentiment signals ({bull_count} bullish vs {bear_count} bearish keyword hits). The news flow is supportive — headline risk appears low, and market perception is constructive. Latest: '{headlines[0][:80]}...'")
        elif bear_count > bull_count:
            msgs.append(f"Sentiment Analyst: News flow for {ticker} is negative ({bear_count} bearish vs {bull_count} bullish signals). This is concerning — negative sentiment creates overhead resistance and discourages institutional buying. Latest: '{headlines[0][:80]}...'")
        else:
            msgs.append(f"Sentiment Analyst: News sentiment for {ticker} is balanced — neither strongly positive nor negative. In the absence of a clear narrative catalyst, technical and fundamental factors will dominate price discovery.")
    else:
        msgs.append(f"Sentiment Analyst: No significant recent news coverage found for {ticker}. Low media attention can be positive (no negative catalysts) or negative (lack of institutional interest). I'll treat this as neutral.")

    if vix > 22:
        msgs.append(f"Sentiment Analyst: India VIX at {vix:.1f} is elevated, signaling market-wide fear. High volatility environments favor defensive positioning — wide bid-ask spreads increase execution costs and gaps can be severe. I'm applying a 20% discount to my sentiment score to account for systemic risk.")
    elif vix > 17:
        msgs.append(f"Sentiment Analyst: VIX at {vix:.1f} is slightly elevated. Market is nervous but not in panic mode. I'd maintain normal position sizing but ensure stop-losses are in place.")
    else:
        msgs.append(f"Sentiment Analyst: VIX at {vix:.1f} indicates a calm market environment — low implied volatility reduces the cost of being wrong. This is a favorable backdrop for initiating new positions.")

    msgs.append(f"Sentiment Analyst: Overall sentiment score {score:+.1f}/10. {'Positive news flow and calm VIX create a supportive sentiment backdrop.' if score > 1.5 else 'Negative sentiment and/or elevated fear create headwinds.' if score < -1.5 else 'Neutral sentiment — fundamentals and technicals will be the deciding factors.'}")
    return msgs


def _mkt_narrative(nifty_pct: float, bank_pct: float, vix: float, score: float) -> list[str]:
    msgs = []
    if nifty_pct > 1.5:
        msgs.append(f"Market Analyst: NIFTY 50 is up a strong {nifty_pct:+.2f}% today — this is a broad bull session with positive risk appetite. In strong market environments, individual stocks tend to outperform their intrinsic fair values as liquidity flows chase momentum. This is a 'rising tide' day.")
    elif nifty_pct > 0:
        msgs.append(f"Market Analyst: NIFTY is modestly positive at {nifty_pct:+.2f}%. The market is constructive but not exuberant — a healthy backdrop that rewards fundamental stock picking over momentum chasing.")
    elif nifty_pct > -1.5:
        msgs.append(f"Market Analyst: NIFTY is down {nifty_pct:.2f}% — mild selling pressure across the board. In this environment, individual stock analysis matters more, but macro headwinds create resistance. Size positions conservatively.")
    else:
        msgs.append(f"Market Analyst: NIFTY is down a significant {nifty_pct:.2f}% — this is a risk-off session. In sell-offs of this magnitude, correlation across stocks rises sharply, and even fundamentally strong stocks can get dragged lower. I'm recommending defensive positioning today.")

    if abs(bank_pct) > 1:
        direction = "leading" if bank_pct > 0 else "underperforming"
        msgs.append(f"Market Analyst: NIFTY Bank is {direction} the broader market at {bank_pct:+.2f}%. {'Banking sector strength signals healthy credit conditions and institutional risk appetite — a positive macro read.' if bank_pct > 0 else 'Banking sector weakness is a yellow flag — financials are the economy, and weakness here often foreshadows broader macro stress.'}")

    msgs.append(f"Market Analyst: Market context score {score:+.1f}/10. {'Market tailwinds support the trade.' if score > 0.5 else 'Market headwinds add risk premium to any position.' if score < -0.5 else 'Market is neutral — stock-specific factors dominate today.'}")
    return msgs


def _build_analyst_report(ticker: str, price: float, d: dict, results: dict) -> str:
    rsi = float(d.get("rsi", 50) or 50)
    macd_h = float(d.get("macd_hist", 0) or 0)
    bb = float(d.get("bb_pct", 0.5) or 0.5)
    sma50 = float(d.get("price_vs_sma50", 0) or 0)
    sma200 = float(d.get("price_vs_sma200", 0) or 0)
    golden = str(d.get("golden_cross", "no")).lower() == "yes"
    pe = d.get("pe_ratio", "N/A")
    roe = d.get("roe")
    tgt = d.get("analyst_target", "N/A")
    hi52 = d.get("52w_high", "N/A")
    lo52 = d.get("52w_low", "N/A")
    news = d.get("headlines", [])

    scores = "\n".join(
        f"   {name:<22} {s:+.2f}/10  {'▲' if s > 2 else '▼' if s < -2 else '─'}"
        for name, (s, _) in results.items()
    )
    combined = sum(s for s, _ in results.values()) / max(len(results), 1)

    return f"""Analyst Team — Comprehensive Report: {ticker.upper()} @ ₹{price:.2f}
{'='*60}

1  TECHNICAL PICTURE
   RSI(14):           {rsi:.1f}  {'← OVERSOLD' if rsi < 35 else '← OVERBOUGHT' if rsi > 70 else '← neutral'}
   MACD Histogram:    {macd_h:+.4f}  {'← bullish crossover' if macd_h > 0 else '← bearish crossover'}
   Bollinger Band %B: {bb:.2f}   {'← near lower band (buy zone)' if bb < 0.25 else '← near upper band (sell zone)' if bb > 0.75 else '← mid-band'}
   vs 50-day SMA:     {sma50:+.1f}%
   vs 200-day SMA:    {sma200:+.1f}%
   Golden Cross:      {'YES — long-term bullish structure confirmed' if golden else 'NO  — 50-SMA below 200-SMA'}

2  FUNDAMENTAL PICTURE
   PE Ratio:          {pe}{"x" if pe != "N/A" else ""}  {'← cheap (<15x)' if pe != "N/A" and float(str(pe)) < 15 else '← premium (>40x)' if pe != "N/A" and float(str(pe)) > 40 else ''}
   ROE:               {f"{float(roe)*100:.1f}%" if roe else "N/A"}  {'← excellent (>20%)' if roe and float(roe)*100 > 20 else '← weak (<8%)' if roe and float(roe)*100 < 8 else ''}
   Analyst Target:    ₹{tgt}  {f"← {((float(str(tgt)) - price)/price*100):+.0f}% from current" if tgt != "N/A" else ""}
   52-Week Range:     ₹{lo52} – ₹{hi52}

3  NEWS & SENTIMENT
{chr(10).join(f"   • {h[:100]}" for h in (news or [])[:4]) or "   No significant news found"}

4  ANALYST SCORES SUMMARY
{scores}
   ─────────────────────────────────────
   Weighted Average:  {combined:+.2f}/10  → {'BUY' if combined > 2 else 'SELL' if combined < -2 else 'HOLD'}

5  PRELIMINARY RECOMMENDATION
   {'Multiple bullish signals align at current price levels. Recommending BUY with defined risk parameters.' if combined > 2 else 'Multiple bearish signals dominate. Recommending SELL or avoid.' if combined < -2 else 'Mixed signals — no clear edge. Recommending HOLD pending Research Team debate.'}
"""


def _build_research_report(bull_t: str, bull_c: list, bear_t: str, bear_r: list,
                            synthesis: str, ticker: str, action: str, score: float) -> str:
    nl = "\n"
    bull_cats = (nl.join(f"   + {c}" for c in bull_c) if bull_c
                 else "   + Technical oversold signals indicate reversal potential" + nl +
                      "   + Fundamental valuation supports entry")
    bear_rsks = (nl.join(f"   - {r}" for r in bear_r) if bear_r
                 else "   - Macro headwinds could suppress recovery" + nl +
                      "   - Stop-loss breach would invalidate bullish thesis")
    consensus = ("Debate favors BULLS — proceed with position." if score > 2
                 else "Debate favors BEARS — avoid or reduce exposure." if score < -2
                 else "Debate inconclusive — HOLD and monitor.")
    bull_default = "Analysis generated by rule engine based on bullish score factors."
    bear_default = "Analysis generated by rule engine based on bearish risk factors."
    synth_default = ("After weighing both arguments, the balance of evidence supports the rule-engine recommendation. "
                     "The bull case is stronger on technical merits; the bear case raises valid tail-risk concerns "
                     "that warrant strict stop-loss discipline.")

    return (f"Research Team — Debate Report: {ticker.upper()}\n"
            f"{'='*60}\n\n"
            f"1  BULL RESEARCHER POSITION  (supporting {action if action == 'BUY' else 'holding'})\n"
            f'   "{bull_t or bull_default}"\n\n'
            f"   Key Catalysts:\n{bull_cats}\n\n"
            f"2  BEAR RESEARCHER COUNTER-ARGUMENT\n"
            f'   "{bear_t or bear_default}"\n\n'
            f"   Key Risks:\n{bear_rsks}\n\n"
            f"3  RESEARCH MANAGER SYNTHESIS\n"
            f'   "{synthesis or synth_default}"\n\n'
            f"4  RESEARCH TEAM CONSENSUS\n"
            f"   Combined conviction score: {score:+.2f}/10 → {consensus}\n")


def _build_risk_report(ticker: str, price: float, action: str, score: float,
                        stop: float, target: float) -> str:
    risk_pct = abs((stop - price) / price * 100)
    reward_pct = abs((target - price) / price * 100)
    rr = reward_pct / risk_pct if risk_pct > 0 else 0
    return f"""Risk Management — Assessment: {ticker.upper()}
{'='*60}

   Action:         {action}  @ ₹{price:.2f}
   Stop-Loss:      ₹{stop:.2f}  ({-risk_pct:.1f}% from entry)
   Target:         ₹{target:.2f}  (+{reward_pct:.1f}% from entry)
   Risk/Reward:    1:{rr:.1f}  {'← favourable (>1:2)' if rr >= 2 else '← acceptable (>1:1.5)' if rr >= 1.5 else '← below threshold'}

   Risky Analyst:  Upside scenario — {reward_pct:.1f}% potential gain if thesis plays out
   Safe Analyst:   Downside scenario — {risk_pct:.1f}% max loss with hard stop at ₹{stop:.2f}
   Neutral Analyst: R/R of 1:{rr:.1f} {'is acceptable. Proceed with standard position sizing.' if rr >= 1.5 else 'is below our 1:2 minimum. Reduce position size by 50%.'}

   RISK VERDICT: {'APPROVED — Risk parameters acceptable.' if rr >= 1.5 else 'CONDITIONAL — Position size must be halved given R/R below threshold.'}
"""


def _build_final_report(ticker: str, price: float, action: str, signal: str, conf: float,
                         score: float, results: dict, bull_t: str, bear_t: str,
                         synthesis: str, stop: float, target: float) -> str:
    risk_pct = abs((stop - price) / price * 100)
    reward_pct = abs((target - price) / price * 100)
    rr = reward_pct / risk_pct if risk_pct > 0 else 0

    scores_str = "\n".join(
        f"   {name:<22} {s:+.2f}/10"
        for name, (s, _) in results.items()
    )

    return f"""Portfolio Management Decision
{'='*60}

   Recommendation: {action} {ticker.upper()} @ ₹{price:.2f}
   Signal Strength: {signal}  |  Conviction: {conf*100:.0f}%

1  SUMMARY OF KEY ARGUMENTS

   Bull Researcher:
   • "{bull_t[:160] if bull_t else 'Technical and fundamental indicators support buying at current levels.'}"

   Bear Researcher:
   • "{bear_t[:160] if bear_t else 'Risks include macro headwinds and the potential for further downside.'}"

   Research Manager:
   • "{synthesis[:200] if synthesis else 'On balance, the bull case has stronger supporting evidence at this price level.'}"

2  RATIONALE FOR {action}
   • Combined analyst score: {score:+.2f}/10 — {'sufficient conviction to act' if abs(score) > 2 else 'borderline — proceed with reduced sizing'}
   • {'Technical and fundamental signals are aligned.' if score > 2 else 'Technical signals dominate the bearish case.' if score < -2 else 'Mixed signals favor patience over action.'}
   • Risk/Reward of 1:{rr:.1f} {'meets' if rr >= 1.5 else 'does not fully meet'} our minimum 1:1.5 threshold

3  ANALYST SCORE BREAKDOWN
{scores_str}
   ──────────────────────────────
   Weighted Combined: {score:+.2f}/10

4  EXECUTION PLAN
   • {'Entry: Market order at ₹' + f'{price:.2f}' + ' (current price)' if action != 'HOLD' else 'No trade — hold current position'}
   • Stop-Loss: ₹{stop:.2f}  (–{risk_pct:.1f}% from entry, hard stop)
   • Target:    ₹{target:.2f}  (+{reward_pct:.1f}% from entry)
   • Position size: {'Standard (full allocation within MAX_POSITION_PCT)' if rr >= 1.5 else 'Half allocation (R/R below threshold)'}
   • Review trigger: {'Re-evaluate if price drops below ₹' + f'{stop*0.98:.2f}' if action != 'HOLD' else 'Re-evaluate on next session'}

   PORTFOLIO MANAGER VERDICT: {'TRADE APPROVED — Proceed with ' + action + '.' if action != 'HOLD' else 'NO TRADE — Conviction insufficient. Revisit on next session.'}
"""


@router.get("/{ticker}")
async def stream_analysis(ticker: str, request: Request, mode: str = "investor"):

    async def generate() -> AsyncGenerator[str, None]:
        tool_calls = 0
        llm_calls = 0
        reports = 0

        yield _sse({"type": "init", "ticker": ticker.upper(), "mode": mode,
                    "agents": [{"team": t, "agent": a, "phase": p, "status": "pending"}
                                for t, a, p in PIPELINE],
                    "stats": {"tool_calls": 0, "llm_calls": 0, "reports": 0}})
        await asyncio.sleep(0.2)

        # ── Gather data ────────────────────────────────────────────────────────
        import yfinance as yf
        from portfolio_ai.data.market_data import compute_technicals, get_fundamentals, get_news_headlines
        from backend.scrapers.nse import nse

        for tool_name, tool_desc in [
            (f'get_live_price("{ticker}")', "Fetching real-time price from NSE"),
            (f'compute_technicals("{ticker}.NS")', "Computing RSI, MACD, Bollinger Bands, SMA"),
            (f'get_fundamentals("{ticker}.NS")', "Fetching PE, ROE, revenue growth, analyst targets"),
            (f'get_news("{ticker}")', "Scanning latest news headlines"),
            ("get_nse_market_data()", "Fetching NIFTY 50, BankNIFTY, India VIX"),
        ]:
            tool_calls += 1
            yield _sse({"type": "tool", "time": _t(), "tool": tool_name,
                        "status": "running", "desc": tool_desc})
            await asyncio.sleep(0.05)

        # Actual fetches
        try:
            price = float(yf.Ticker(f"{ticker}.NS").fast_info.last_price or 0)
        except Exception:
            price = 0.0
        yield _sse({"type": "tool", "time": _t(), "tool": f'get_live_price("{ticker}")',
                    "result": f"₹{price:.2f}", "status": "done"})

        try:
            tech = compute_technicals(f"{ticker}.NS")
        except Exception:
            tech = {}
        rsi_val = tech.get("rsi_14", "N/A")
        rsi_str = f"{float(rsi_val):.1f}" if rsi_val != "N/A" else "N/A"
        yield _sse({"type": "tool", "time": _t(), "tool": f'compute_technicals("{ticker}.NS")',
                    "result": f"RSI={rsi_str} | MACD_HIST={tech.get('macd_histogram','N/A')} | BB%={tech.get('bb_pct_b','N/A')}",
                    "status": "done"})

        try:
            fund = get_fundamentals(f"{ticker}.NS")
        except Exception:
            fund = {}
        roe_val = fund.get("roe")
        roe_str = f"{float(roe_val)*100:.1f}%" if roe_val else "N/A"
        yield _sse({"type": "tool", "time": _t(), "tool": f'get_fundamentals("{ticker}.NS")',
                    "result": f"PE={fund.get('pe_ratio','N/A')} | ROE={roe_str} | Target=Rs.{fund.get('analyst_target','N/A')}",
                    "status": "done"})

        try:
            headlines = get_news_headlines(ticker, max_items=5)
        except Exception:
            headlines = []
        yield _sse({"type": "tool", "time": _t(), "tool": f'get_news("{ticker}")',
                    "result": f"{len(headlines)} headlines: {headlines[0][:60] + '...' if headlines else 'none'}",
                    "status": "done"})

        try:
            indices = await nse.all_indices()
            nifty = next((i for i in indices if i.get("indexSymbol") == "NIFTY 50"), {})
            bank  = next((i for i in indices if i.get("indexSymbol") == "NIFTY BANK"), {})
            vix_i = next((i for i in indices if i.get("indexSymbol") == "INDIA VIX"), {})
            nifty_pct = float(nifty.get("percentChange", 0) or 0)
            bank_pct  = float(bank.get("percentChange", 0) or 0)
            vix       = float(vix_i.get("last", 15) or 15)
        except Exception:
            nifty_pct = bank_pct = 0.0; vix = 15.0
        yield _sse({"type": "tool", "time": _t(), "tool": "get_nse_market_data()",
                    "result": f"NIFTY {nifty_pct:+.2f}% | BANK {bank_pct:+.2f}% | VIX {vix:.1f}",
                    "status": "done"})

        yield _sse({"type": "stats", "tool_calls": tool_calls, "llm_calls": llm_calls, "reports": reports})
        await asyncio.sleep(0.3)

        # ── Build stock_data dict ──────────────────────────────────────────────
        stock_data = {
            "rsi": tech.get("rsi_14", 50), "macd_hist": tech.get("macd_histogram", 0),
            "macd": tech.get("macd", 0), "macd_signal": tech.get("macd_signal", 0),
            "bb_pct": tech.get("bb_pct_b", 0.5),
            "price_vs_sma50": tech.get("price_vs_sma50", 0),
            "price_vs_sma200": tech.get("price_vs_sma200", 0),
            "golden_cross": tech.get("golden_cross", "no"),
            "pe_ratio": fund.get("pe_ratio"), "roe": fund.get("roe"),
            "revenue_growth": fund.get("revenue_growth"),
            "analyst_target": fund.get("analyst_target"),
            "52w_high": fund.get("52w_high"), "52w_low": fund.get("52w_low"),
            "profit_margin": fund.get("profit_margin"),
            "price": price, "headlines": headlines,
        }

        from backend.agents.rule_based_trader import (
            technical_analyst, fundamental_analyst, momentum_analyst,
            sentiment_analyst, market_analyst,
        )
        analyst_results: dict[str, tuple[float, str]] = {}

        # ── Technical Analyst ─────────────────────────────────────────────────
        yield _sse({"type": "agent_status", "team": "Analyst Team", "agent": "Technical Analyst", "status": "in_progress"})
        t_score, t_reason = technical_analyst(stock_data)
        analyst_results["Technical Analyst"] = (t_score, t_reason)
        for msg in _tech_narrative(ticker, price, stock_data, t_score):
            yield _sse({"type": "message", "time": _t(), "msg_type": "Reasoning", "agent": "Technical Analyst", "content": msg})
            await asyncio.sleep(0.12)
        yield _sse({"type": "agent_status", "team": "Analyst Team", "agent": "Technical Analyst", "status": "completed", "score": round(t_score, 2)})
        await asyncio.sleep(0.2)

        # ── Fundamental Analyst ───────────────────────────────────────────────
        yield _sse({"type": "agent_status", "team": "Analyst Team", "agent": "Fundamental Analyst", "status": "in_progress"})
        f_score, f_reason = fundamental_analyst(stock_data)
        analyst_results["Fundamental Analyst"] = (f_score, f_reason)
        for msg in _fund_narrative(ticker, price, stock_data, f_score):
            yield _sse({"type": "message", "time": _t(), "msg_type": "Reasoning", "agent": "Fundamental Analyst", "content": msg})
            await asyncio.sleep(0.12)
        yield _sse({"type": "agent_status", "team": "Analyst Team", "agent": "Fundamental Analyst", "status": "completed", "score": round(f_score, 2)})
        await asyncio.sleep(0.2)

        # ── Momentum Analyst ──────────────────────────────────────────────────
        yield _sse({"type": "agent_status", "team": "Analyst Team", "agent": "Momentum Analyst", "status": "in_progress"})
        m_score, m_reason = momentum_analyst(stock_data)
        analyst_results["Momentum Analyst"] = (m_score, m_reason)
        for msg in _mom_narrative(ticker, price, stock_data, m_score):
            yield _sse({"type": "message", "time": _t(), "msg_type": "Reasoning", "agent": "Momentum Analyst", "content": msg})
            await asyncio.sleep(0.12)
        yield _sse({"type": "agent_status", "team": "Analyst Team", "agent": "Momentum Analyst", "status": "completed", "score": round(m_score, 2)})
        await asyncio.sleep(0.2)

        # ── Sentiment Analyst ─────────────────────────────────────────────────
        yield _sse({"type": "agent_status", "team": "Analyst Team", "agent": "Sentiment Analyst", "status": "in_progress"})
        s_score, s_reason = sentiment_analyst(headlines, vix)
        analyst_results["Sentiment Analyst"] = (s_score, s_reason)
        for msg in _sent_narrative(ticker, headlines, vix, s_score):
            yield _sse({"type": "message", "time": _t(), "msg_type": "Reasoning", "agent": "Sentiment Analyst", "content": msg})
            await asyncio.sleep(0.12)
        yield _sse({"type": "agent_status", "team": "Analyst Team", "agent": "Sentiment Analyst", "status": "completed", "score": round(s_score, 2)})
        await asyncio.sleep(0.2)

        # ── Market Analyst ────────────────────────────────────────────────────
        yield _sse({"type": "agent_status", "team": "Analyst Team", "agent": "Market Analyst", "status": "in_progress"})
        mk_score, mk_reason = market_analyst(nifty_pct, bank_pct, None)
        analyst_results["Market Analyst"] = (mk_score, mk_reason)
        for msg in _mkt_narrative(nifty_pct, bank_pct, vix, mk_score):
            yield _sse({"type": "message", "time": _t(), "msg_type": "Reasoning", "agent": "Market Analyst", "content": msg})
            await asyncio.sleep(0.12)
        yield _sse({"type": "agent_status", "team": "Analyst Team", "agent": "Market Analyst", "status": "completed", "score": round(mk_score, 2)})

        # Analyst team report
        reports += 1
        analyst_rpt = _build_analyst_report(ticker, price, stock_data, analyst_results)
        yield _sse({"type": "report", "title": f"Analyst Team Report — {ticker.upper()}", "content": analyst_rpt})
        yield _sse({"type": "stats", "tool_calls": tool_calls, "llm_calls": llm_calls, "reports": reports})
        await asyncio.sleep(0.3)

        # ── Research Team ─────────────────────────────────────────────────────
        weights = {"Technical Analyst": 0.25, "Fundamental Analyst": 0.40,
                   "Momentum Analyst": 0.15, "Sentiment Analyst": 0.12, "Market Analyst": 0.08}
        combined = sum(analyst_results[a][0] * weights.get(a, 0.1) for a in analyst_results if a in weights)

        bull_thesis = bear_thesis = research_conclusion = ""
        bull_catalysts: list[str] = []
        bear_risks: list[str] = []

        from backend.models.config import load_config
        import os as _os
        cfg = load_config()
        _env_map = {"anthropic": "ANTHROPIC_API_KEY", "google": "GOOGLE_API_KEY", "openai": "OPENAI_API_KEY"}
        resolved_key = cfg.llm_api_key or _os.environ.get(_env_map.get(cfg.llm_provider, ""), "")
        if resolved_key:
            cfg.llm_api_key = resolved_key

        if resolved_key:
            llm_calls += 1
            action_hint = "BUY" if combined >= 2 else "SELL" if combined <= -2 else "HOLD"
            yield _sse({"type": "agent_status", "team": "Research Team", "agent": "Bull Researcher", "status": "in_progress"})
            yield _sse({"type": "agent_status", "team": "Research Team", "agent": "Bear Researcher", "status": "in_progress"})
            yield _sse({"type": "agent_status", "team": "Research Team", "agent": "Research Manager", "status": "in_progress"})
            yield _sse({"type": "message", "time": _t(), "msg_type": "Tool", "agent": "Research Team",
                        "content": f'call_llm("{cfg.llm_model or "haiku"}", research_debate("{ticker}", action_hint="{action_hint}"), max_tokens=600)'})
            yield _sse({"type": "stats", "tool_calls": tool_calls, "llm_calls": llm_calls, "reports": reports})

            debate = await _claude_research_debate(ticker, price, stock_data, combined, cfg)
            bull_thesis = debate.get("bull_thesis", "")
            bull_catalysts = debate.get("bull_catalysts", [])
            bear_thesis = debate.get("bear_thesis", "")
            bear_risks = debate.get("bear_risks", [])
            research_conclusion = debate.get("research_conclusion", "")

            for line in (bull_thesis or "").split(". "):
                if line.strip():
                    yield _sse({"type": "message", "time": _t(), "msg_type": "Reasoning",
                                "agent": "Bull Researcher", "content": f"Bull Researcher: {line.strip()}."})
                    await asyncio.sleep(0.1)
            yield _sse({"type": "agent_status", "team": "Research Team", "agent": "Bull Researcher", "status": "completed"})

            for line in (bear_thesis or "").split(". "):
                if line.strip():
                    yield _sse({"type": "message", "time": _t(), "msg_type": "Reasoning",
                                "agent": "Bear Researcher", "content": f"Bear Researcher: {line.strip()}."})
                    await asyncio.sleep(0.1)
            yield _sse({"type": "agent_status", "team": "Research Team", "agent": "Bear Researcher", "status": "completed"})

            for line in (research_conclusion or "").split(". "):
                if line.strip():
                    yield _sse({"type": "message", "time": _t(), "msg_type": "Reasoning",
                                "agent": "Research Manager", "content": f"Research Manager: {line.strip()}."})
                    await asyncio.sleep(0.1)
            yield _sse({"type": "agent_status", "team": "Research Team", "agent": "Research Manager", "status": "completed"})

        else:
            # No LLM — generate rule-based research debate
            bull_thesis = (f"I see strong evidence supporting a {('BUY' if combined > 0 else 'cautious')} stance on {ticker}. "
                           f"The technical score of {analyst_results.get('Technical Analyst',(0,''))[0]:+.1f}/10 "
                           f"combined with fundamentals at {analyst_results.get('Fundamental Analyst',(0,''))[0]:+.1f}/10 "
                           f"suggests {'accumulation is warranted' if combined > 2 else 'wait for better entry'}.")
            bull_catalysts = ["Technical oversold bounce potential", "Institutional support near current levels"]
            bear_thesis = (f"I push back on the bullish thesis. Market context score of "
                           f"{analyst_results.get('Market Analyst',(0,''))[0]:+.1f}/10 and "
                           f"sentiment at {analyst_results.get('Sentiment Analyst',(0,''))[0]:+.1f}/10 "
                           f"warn of macro headwinds that could invalidate stock-specific signals.")
            bear_risks = ["Macro-driven selling could overwhelm technical signals", "Stop-loss breach would invalidate thesis"]
            research_conclusion = (f"After weighing both arguments, the combined score of {combined:+.2f}/10 "
                                    f"{'supports the bull case with adequate conviction' if combined > 2 else 'supports the bear case' if combined < -2 else 'is insufficient for conviction — HOLD'}. "
                                    "Strict stop-loss discipline is non-negotiable.")

            for agent in ["Bull Researcher", "Bear Researcher", "Research Manager"]:
                yield _sse({"type": "agent_status", "team": "Research Team", "agent": agent, "status": "in_progress"})
            for msg, agent in [(bull_thesis, "Bull Researcher"), (bear_thesis, "Bear Researcher"), (research_conclusion, "Research Manager")]:
                yield _sse({"type": "message", "time": _t(), "msg_type": "Reasoning", "agent": agent,
                            "content": f"{agent}: {msg}"})
                await asyncio.sleep(0.15)
                yield _sse({"type": "agent_status", "team": "Research Team", "agent": agent, "status": "completed"})
            yield _sse({"type": "message", "time": _t(), "msg_type": "Tool", "agent": "Research Team",
                        "content": f"⚠ No LLM key — rule-based debate used. Add key at Setup → Step 3 for Claude-powered debate."})

        reports += 1
        res_rpt = _build_research_report(bull_thesis, bull_catalysts, bear_thesis, bear_risks,
                                          research_conclusion, ticker, "BUY" if combined > 2 else "SELL" if combined < -2 else "HOLD", combined)
        yield _sse({"type": "report", "title": "Research Team Debate Report", "content": res_rpt})
        yield _sse({"type": "stats", "tool_calls": tool_calls, "llm_calls": llm_calls, "reports": reports})
        await asyncio.sleep(0.3)

        # ── Trader ────────────────────────────────────────────────────────────
        yield _sse({"type": "agent_status", "team": "Trading Team", "agent": "Trader", "status": "in_progress"})
        action = "BUY" if combined >= 2.0 else "SELL" if combined <= -2.0 else "HOLD"
        signal = ("STRONG_BUY" if combined >= 4.5 else "BUY" if combined >= 2 else
                  "STRONG_SELL" if combined <= -4.5 else "SELL" if combined <= -2 else "HOLD")
        yield _sse({"type": "message", "time": _t(), "msg_type": "Reasoning", "agent": "Trader",
                    "content": f"Trader: After synthesizing all analyst reports and the research debate, my proposed action is {action} on {ticker.upper()} at ₹{price:.2f}. Combined conviction score: {combined:+.2f}/10 → {signal}. {'The bull case is well-supported by convergent signals.' if combined > 2 else 'The bear case has enough supporting evidence to recommend selling.' if combined < -2 else 'The debate was too close to call — I propose holding and reassessing next session.'}"})
        yield _sse({"type": "agent_status", "team": "Trading Team", "agent": "Trader", "status": "completed"})
        await asyncio.sleep(0.2)

        # ── Risk Management ───────────────────────────────────────────────────
        stop_loss   = round(price * 0.92, 2)
        take_profit = round(price * 1.20, 2)
        risk_pct    = abs((stop_loss - price) / price * 100)
        reward_pct  = abs((take_profit - price) / price * 100)
        rr = reward_pct / risk_pct if risk_pct > 0 else 0

        for agent, msg in [
            ("Risky Analyst",
             f"Risky Analyst: I see the {('bullish signals from ' + ', '.join([a for a, (s,_) in analyst_results.items() if s > 2][:2])) if combined > 0 else ('bearish pressure across technicals and sentiment')} as the primary driver here. "
             f"Upside target ₹{take_profit:.2f} (+{reward_pct:.1f}%) is achievable within 4-6 weeks if the thesis holds. "
             f"{'The Golden Cross and oversold RSI give me confidence to maintain standard sizing.' if analyst_results.get('Technical Analyst',(0,''))[0] > 2 else 'I recommend reducing position to 50% given mixed signals.'}"),
            ("Safe Analyst",
             f"Safe Analyst: I need to push back on any excessive risk-taking here. "
             f"Stop-loss must be firmly placed at ₹{stop_loss:.2f} — a {risk_pct:.1f}% maximum drawdown. "
             f"{'With VIX at ' + f'{vix:.1f}' + ', volatility is ' + ('elevated and unpredictable, warranting tighter stops.' if vix > 20 else 'manageable — standard position sizing is acceptable.')} "
             f"{'The bear case raised valid concerns about macro headwinds that could quickly invalidate the bull thesis.' if combined < 4 else 'Even with high conviction, risk management discipline is non-negotiable.'}"),
            ("Neutral Analyst",
             f"Neutral Analyst: Both the Risky and Safe Analysts make valid points. "
             f"Risk/Reward of 1:{rr:.1f} {'meets our minimum threshold of 1:1.5 — proceed with standard allocation.' if rr >= 1.5 else 'falls below the 1:1.5 minimum — I propose half-sizing this position.'} "
             f"The combined analyst score of {combined:+.2f}/10 {'provides sufficient conviction for a full position.' if abs(combined) > 4 else 'suggests moderate conviction — reduce position size accordingly.'}"),
        ]:
            yield _sse({"type": "agent_status", "team": "Risk Management", "agent": agent, "status": "in_progress"})
            await asyncio.sleep(0.1)
            yield _sse({"type": "message", "time": _t(), "msg_type": "Reasoning", "agent": agent, "content": msg})
            await asyncio.sleep(0.1)
            yield _sse({"type": "agent_status", "team": "Risk Management", "agent": agent, "status": "completed"})

        reports += 1
        risk_rpt = _build_risk_report(ticker, price, action, combined, stop_loss, take_profit)
        yield _sse({"type": "report", "title": "Risk Management Assessment", "content": risk_rpt})

        # ── Portfolio Manager ─────────────────────────────────────────────────
        yield _sse({"type": "agent_status", "team": "Portfolio Mgmt", "agent": "Portfolio Manager", "status": "in_progress"})
        confidence = min(abs(combined) / 10, 0.95)
        yield _sse({"type": "message", "time": _t(), "msg_type": "Reasoning", "agent": "Portfolio Manager",
                    "content": (f"Portfolio Manager: I have reviewed all analyst reports, the research debate, trader recommendation, and risk assessment. "
                                f"The weight of evidence {'strongly supports a {action} on ' + ticker.upper() + ' at ₹' + f'{price:.2f}' if abs(combined) > 3 else 'marginally supports ' + action if abs(combined) > 2 else 'does not provide sufficient conviction — I am choosing HOLD'}. "
                                f"{'I am particularly influenced by the ' + (', '.join([a for a, (s,_) in sorted(analyst_results.items(), key=lambda x: abs(x[1][0]), reverse=True)[:2]]) + ' findings') if analyst_results else ''} "
                                f"and the Research Manager's conclusion: '{research_conclusion[:100] if research_conclusion else 'Rule-based synthesis applied'}...'")})
        yield _sse({"type": "agent_status", "team": "Portfolio Mgmt", "agent": "Portfolio Manager", "status": "completed"})

        reports += 1
        final_rpt = _build_final_report(ticker, price, action, signal, confidence, combined,
                                         analyst_results, bull_thesis, bear_thesis,
                                         research_conclusion, stop_loss, take_profit)
        yield _sse({"type": "report", "title": "Portfolio Management Decision", "content": final_rpt})
        yield _sse({"type": "stats", "tool_calls": tool_calls, "llm_calls": llm_calls, "reports": reports})

        yield _sse({"type": "done", "ticker": ticker.upper(), "action": action, "signal": signal,
                    "confidence": round(confidence, 2), "combined_score": round(combined, 2),
                    "price": price, "stop_loss": stop_loss, "take_profit": take_profit,
                    "stats": {"tool_calls": tool_calls, "llm_calls": llm_calls, "reports": reports}})

    return StreamingResponse(generate(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


async def _claude_research_debate(ticker: str, price: float, data: dict, score: float, cfg) -> dict:
    from backend.utils import cache as llm_cache
    import httpx

    cache_key = f"debate:{ticker}:{round(score, 1)}"
    cached = llm_cache.get(cache_key)
    if cached:
        return cached

    action = "BUY" if score >= 2 else "SELL" if score <= -2 else "HOLD"
    rsi = data.get("rsi", 50); macd = data.get("macd_hist", 0)
    pe = data.get("pe_ratio", "N/A"); roe = round((data.get("roe") or 0) * 100, 1)
    tgt = data.get("analyst_target", "N/A"); news = data.get("headlines", [])

    prompt = f"""{ticker} @ ₹{price:.2f} | Rule engine: {action} (score {score:+.2f}/10)
Tech: RSI={rsi:.1f} MACD_HIST={macd:.3f} | Fund: PE={pe} ROE={roe}% Target=₹{tgt}
News: {' | '.join(news[:2])}

You are three analysts debating this trade. Respond with this exact JSON (no markdown):
{{
  "bull_thesis": "<2-3 sentences: Bull Researcher's strongest argument FOR {action}, citing specific numbers from the data above>",
  "bull_catalysts": ["<specific catalyst 1 with data>", "<specific catalyst 2>"],
  "bear_thesis": "<2-3 sentences: Bear Researcher's strongest counter-argument AGAINST {action}, citing specific risks>",
  "bear_risks": ["<specific risk 1 with data>", "<specific risk 2>"],
  "research_conclusion": "<2-3 sentences: Research Manager's synthesis — who wins the debate and why, with final recommendation>"
}}"""

    try:
        if cfg.llm_provider == "anthropic":
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.post("https://api.anthropic.com/v1/messages",
                    headers={"x-api-key": cfg.llm_api_key, "anthropic-version": "2023-06-01"},
                    json={"model": cfg.llm_model or "claude-haiku-4-5-20251001", "max_tokens": 600,
                          "system": "You are a financial analyst debate facilitator. Always respond with valid JSON only, no markdown.",
                          "messages": [{"role": "user", "content": prompt}]})
            raw = r.json()["content"][0]["text"].strip() if r.status_code == 200 else "{}"
        elif cfg.llm_provider == "google":
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{cfg.llm_model or 'gemini-2.0-flash-lite'}:generateContent?key={cfg.llm_api_key}",
                    json={"contents": [{"parts": [{"text": "Financial analyst. JSON only, no markdown.\n" + prompt}]}],
                          "generationConfig": {"maxOutputTokens": 600, "temperature": 0.2}})
            raw = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip() if r.status_code == 200 else "{}"
        elif cfg.llm_provider == "openai":
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.post("https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {cfg.llm_api_key}"},
                    json={"model": cfg.llm_model or "gpt-4o-mini", "max_tokens": 600, "temperature": 0.2,
                          "messages": [{"role": "system", "content": "JSON only, no markdown."},
                                       {"role": "user", "content": prompt}]})
            raw = r.json()["choices"][0]["message"]["content"].strip() if r.status_code == 200 else "{}"
        else:
            return {}

        if "```" in raw:
            parts = raw.split("```")
            raw = parts[1][4:] if len(parts) > 1 and parts[1].startswith("json") else parts[1] if len(parts) > 1 else raw
        result = json.loads(raw)
        llm_cache.set(cache_key, result, ttl_seconds=3600)
        return result
    except Exception:
        return {}
