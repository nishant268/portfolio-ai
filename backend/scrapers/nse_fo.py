"""
NSE Futures & Options data scraper.
Primary: NSE website API (works on Indian IPs).
Fallback: Kiteconnect instruments + Black-Scholes theoretical pricing when NSE is blocked.
"""
from __future__ import annotations

import asyncio
import math
from datetime import date
from typing import Any

from backend.scrapers.nse import nse


# ── Black-Scholes helpers (no external deps) ──────────────────────────────────

def _norm_cdf(x: float) -> float:
    """Cumulative standard normal distribution (Abramowitz & Stegun approximation)."""
    t = 1.0 / (1.0 + 0.2316419 * abs(x))
    poly = t * (0.319381530 + t * (-0.356563782 + t * (1.781477937 + t * (-1.821255978 + t * 1.330274429))))
    pdf = math.exp(-x * x / 2.0) / math.sqrt(2.0 * math.pi)
    cdf = 1.0 - pdf * poly
    return cdf if x >= 0 else 1.0 - cdf


def _bs_price(S: float, K: float, T: float, sigma: float, r: float = 0.065,
              option_type: str = "call") -> float:
    """Black-Scholes European option price."""
    if T <= 0:
        return max(0.0, S - K) if option_type == "call" else max(0.0, K - S)
    sqrt_T = math.sqrt(T)
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * sqrt_T)
    d2 = d1 - sigma * sqrt_T
    if option_type == "call":
        return S * _norm_cdf(d1) - K * math.exp(-r * T) * _norm_cdf(d2)
    return K * math.exp(-r * T) * _norm_cdf(-d2) - S * _norm_cdf(-d1)


def _bs_iv(price: float, S: float, K: float, T: float, r: float = 0.065,
           option_type: str = "call") -> float:
    """Implied volatility via bisection (returns annualised σ)."""
    if T <= 0 or price <= 0:
        return 0.0
    lo, hi = 0.001, 5.0
    for _ in range(50):
        mid = (lo + hi) / 2
        if _bs_price(S, K, T, mid, r, option_type) > price:
            hi = mid
        else:
            lo = mid
    return round((lo + hi) / 2, 4)


# ── Kiteconnect fallback ──────────────────────────────────────────────────────

async def _kite_option_chain(symbol: str) -> dict[str, Any]:
    """
    Build option chain from Kiteconnect instruments + Black-Scholes prices.
    Returns the same schema as the NSE scraper so callers stay unchanged.
    Adds `is_theoretical: True` to indicate live OI is unavailable.
    """
    loop = asyncio.get_event_loop()

    def _build() -> dict[str, Any]:
        from backend.models.config import load_config
        cfg = load_config()
        if not cfg.zerodha.api_key or not cfg.zerodha.access_token:
            return {"error": "Zerodha not configured — option chain unavailable"}

        from kiteconnect import KiteConnect
        kite = KiteConnect(api_key=cfg.zerodha.api_key)
        kite.set_access_token(cfg.zerodha.access_token)

        # Map symbol to kiteconnect name
        sym_map = {"BANKNIFTY": "BANKNIFTY", "FINNIFTY": "FINNIFTY",
                   "MIDCPNIFTY": "MIDCPNIFTY", "NIFTYNXT50": "NIFTYNXT50"}
        kite_name = sym_map.get(symbol.upper(), "NIFTY")

        instruments = kite.instruments("NFO")
        options = [i for i in instruments
                   if i["name"] == kite_name and i["instrument_type"] in ("CE", "PE")]
        if not options:
            return {"error": f"No instruments found for {kite_name}"}

        expiries = sorted(set(i["expiry"] for i in options))
        nearest = expiries[0]
        near = [i for i in options if i["expiry"] == nearest]
        strikes = sorted(set(i["strike"] for i in near))
        expiry_strs = [str(e) for e in expiries[:3]]

        # Get underlying from allIndices
        import yfinance as yf
        yf_map = {"NIFTY": "^NSEI", "BANKNIFTY": "^NSEBANK",
                  "FINNIFTY": "NIFTY_FIN_SERVICE.NS", "MIDCPNIFTY": "^CNXMIDCAP"}
        try:
            spot = float(yf.Ticker(yf_map.get(kite_name, "^NSEI")).fast_info.last_price or 0)
        except Exception:
            spot = 0.0

        # Get VIX for sigma estimate
        vix = 15.0
        try:
            t_vix = yf.Ticker("^INDIAVIX")
            vix = float(t_vix.fast_info.last_price or 15.0)
        except Exception:
            pass
        sigma = vix / 100.0  # annualised volatility

        # Days to expiry
        today = date.today()
        dte = max((nearest - today).days, 0)
        T = dte / 365.0

        # Generate ATM ± 5% strikes
        if spot > 0:
            atm = min(strikes, key=lambda k: abs(k - spot))
            idx = strikes.index(atm)
            selected = strikes[max(0, idx - 5): idx + 6]
        else:
            selected = strikes[:10]

        top_strikes = []
        for k in selected:
            ce_ltp = round(_bs_price(spot, k, T, sigma, option_type="call"), 2) if spot > 0 else 0
            pe_ltp = round(_bs_price(spot, k, T, sigma, option_type="put"), 2) if spot > 0 else 0
            ce_iv  = round(sigma * 100, 2) if spot > 0 else 0
            pe_iv  = round(sigma * 100, 2) if spot > 0 else 0
            top_strikes.append({
                "strike": k, "ce_oi": 0, "ce_ltp": ce_ltp, "ce_iv": ce_iv,
                "pe_oi": 0, "pe_ltp": pe_ltp, "pe_iv": pe_iv,
            })

        # Theoretical PCR ≈ delta ratio (for ATM: CE_delta ≈ 0.5, PE_delta ≈ -0.5 → PCR ≈ 1)
        pcr = 1.0  # theoretical ATM PCR

        return {
            "symbol": kite_name,
            "underlying": round(spot, 2),
            "expiry": expiry_strs,
            "pcr": pcr,
            "max_pain": 0.0,       # not computable without real OI
            "total_ce_oi": 0,
            "total_pe_oi": 0,
            "top_strikes": top_strikes,
            "is_theoretical": True,
            "vix": round(vix, 2),
            "dte": dte,
        }

    try:
        return await loop.run_in_executor(None, _build)
    except Exception as e:
        return {"error": str(e)}


# ── Public API ────────────────────────────────────────────────────────────────

async def option_chain(symbol: str) -> dict[str, Any]:
    """
    Full option chain.
    1. Tries NSE API (works on Indian IPs / direct NSE access).
    2. Falls back to Kiteconnect + Black-Scholes when NSE is blocked.
    """
    _INDEX_SYMBOLS = {"NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "NIFTYNXT50"}
    endpoint = (
        f"/api/option-chain-indices?symbol={symbol.upper()}"
        if symbol.upper() in _INDEX_SYMBOLS
        else f"/api/option-chain-equities?symbol={symbol.upper()}"
    )

    raw = await nse._aget(endpoint)
    records    = raw.get("records", {}) if not raw.get("error") else {}
    all_strikes = records.get("data", [])

    # If NSE returned real data — parse and return it
    if all_strikes:
        filtered     = raw.get("filtered", {})
        underlying   = records.get("underlyingValue", 0)
        expiry_dates = records.get("expiryDates", [])

        nearest_expiry = expiry_dates[0] if expiry_dates else None
        strikes = (
            [s for s in all_strikes if s.get("expiryDate") == nearest_expiry]
            if nearest_expiry else all_strikes
        ) or all_strikes

        ce_oi = filtered.get("CE", {}).get("totOI", 0)
        pe_oi = filtered.get("PE", {}).get("totOI", 0)
        if not ce_oi and not pe_oi:
            ce_oi = sum(s.get("CE", {}).get("openInterest", 0) for s in strikes)
            pe_oi = sum(s.get("PE", {}).get("openInterest", 0) for s in strikes)

        pcr = round(pe_oi / ce_oi, 2) if ce_oi else 0
        top = sorted(
            strikes,
            key=lambda x: (x.get("CE", {}).get("openInterest", 0) + x.get("PE", {}).get("openInterest", 0)),
            reverse=True,
        )[:10]

        return {
            "symbol": symbol.upper(),
            "underlying": underlying,
            "expiry": expiry_dates[:3],
            "pcr": pcr,
            "max_pain": _max_pain(strikes),
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
            "is_theoretical": False,
        }

    # NSE blocked → fall back to Kiteconnect + Black-Scholes
    return await _kite_option_chain(symbol)


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
