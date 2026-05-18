"""
NSE Futures & Options data scraper.
Uses the same curl_cffi session as the main NSE scraper.
"""
from __future__ import annotations

import asyncio
from typing import Any

from backend.scrapers.nse import nse


async def option_chain(symbol: str) -> dict[str, Any]:
    """Full option chain. Uses indices endpoint for NIFTY/BANKNIFTY, equities for stocks."""
    _INDEX_SYMBOLS = {"NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "NIFTYNXT50"}
    endpoint = (
        f"/api/option-chain-indices?symbol={symbol.upper()}"
        if symbol.upper() in _INDEX_SYMBOLS
        else f"/api/option-chain-equities?symbol={symbol.upper()}"
    )
    raw = await nse._aget(endpoint)
    if "error" in raw:
        return raw

    records = raw.get("records", {})
    filtered = raw.get("filtered", {})
    strikes = records.get("data", [])
    underlying = records.get("underlyingValue", 0)

    # Summarise into a compact structure
    ce_oi = filtered.get("CE", {}).get("totOI", 0)
    pe_oi = filtered.get("PE", {}).get("totOI", 0)
    pcr = round(pe_oi / ce_oi, 2) if ce_oi else 0

    # Max pain: strike with minimum total loss for option writers
    max_pain_strike = _max_pain(strikes)

    # Top 5 strikes by CE + PE OI
    top = sorted(
        strikes,
        key=lambda x: (x.get("CE", {}).get("openInterest", 0) + x.get("PE", {}).get("openInterest", 0)),
        reverse=True,
    )[:10]

    return {
        "symbol": symbol.upper(),
        "underlying": underlying,
        "expiry": records.get("expiryDates", [])[:3],
        "pcr": pcr,
        "max_pain": max_pain_strike,
        "total_ce_oi": ce_oi,
        "total_pe_oi": pe_oi,
        "top_strikes": [
            {
                "strike": s.get("strikePrice"),
                "ce_oi": s.get("CE", {}).get("openInterest", 0),
                "ce_ltp": s.get("CE", {}).get("lastPrice", 0),
                "ce_iv": s.get("CE", {}).get("impliedVolatility", 0),
                "pe_oi": s.get("PE", {}).get("openInterest", 0),
                "pe_ltp": s.get("PE", {}).get("lastPrice", 0),
                "pe_iv": s.get("PE", {}).get("impliedVolatility", 0),
            }
            for s in top
        ],
    }


async def fii_dii_data() -> dict[str, Any]:
    return await nse._aget("/api/fiidiiTradeReact")


async def fo_market_watch(symbol: str = "NIFTY") -> dict[str, Any]:
    return await nse._aget(f"/api/quote-derivative?symbol={symbol.upper()}")


async def futures_strip(symbol: str = "NIFTY") -> list[dict[str, Any]]:
    """Near / mid / far month futures for a symbol."""
    raw = await fo_market_watch(symbol)
    stocks = raw.get("stocks", [])
    futures = [
        s for s in stocks
        if s.get("metadata", {}).get("instrumentType") == "Index Futures"
        or "FUT" in s.get("metadata", {}).get("instrumentType", "")
    ]
    return [
        {
            "expiry": f.get("metadata", {}).get("expiryDate"),
            "ltp": f.get("underlyingValue") or f.get("metadata", {}).get("lastPrice"),
            "change_pct": f.get("metadata", {}).get("pChange"),
            "oi": f.get("marketDeptOrderBook", {}).get("totalSellQuantity"),
        }
        for f in futures[:3]
    ]


def _max_pain(strikes: list[dict]) -> float:
    """Calculate max pain price from options chain data."""
    if not strikes:
        return 0.0
    strike_prices = sorted({s.get("strikePrice", 0) for s in strikes})
    pain_map: dict[float, float] = {}
    for test_price in strike_prices:
        total_pain = 0.0
        for s in strikes:
            sp = s.get("strikePrice", 0)
            ce = s.get("CE", {}).get("openInterest", 0)
            pe = s.get("PE", {}).get("openInterest", 0)
            if test_price > sp:
                total_pain += ce * (test_price - sp)
            elif test_price < sp:
                total_pain += pe * (sp - test_price)
        pain_map[test_price] = total_pain
    return min(pain_map, key=lambda k: pain_map[k])
