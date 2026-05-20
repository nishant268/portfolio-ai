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
    Build option chain from Kiteconnect instruments + live quotes.
    Uses kite.quote() for real OI/LTP; falls back to Black-Scholes when market is closed.
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

        import yfinance as yf
        yf_map = {"NIFTY": "^NSEI", "BANKNIFTY": "^NSEBANK",
                  "FINNIFTY": "NIFTY_FIN_SERVICE.NS", "MIDCPNIFTY": "^CNXMIDCAP"}
        try:
            spot = float(yf.Ticker(yf_map.get(kite_name, "^NSEI")).fast_info.last_price or 0)
        except Exception:
            spot = 0.0

        vix = 15.0
        try:
            vix = float(yf.Ticker("^INDIAVIX").fast_info.last_price or 15.0)
        except Exception:
            pass
        sigma = vix / 100.0

        today = date.today()
        dte = max((nearest - today).days, 0)
        T = dte / 365.0

        if spot > 0:
            atm = min(strikes, key=lambda k: abs(k - spot))
            idx = strikes.index(atm)
            selected = strikes[max(0, idx - 5): idx + 6]
        else:
            selected = strikes[:10]

        # Build tradingsymbol lookup: (strike, type) → tradingsymbol
        sym_lookup: dict[tuple, str] = {}
        for i in near:
            if i["strike"] in selected:
                sym_lookup[(i["strike"], i["instrument_type"])] = i["tradingsymbol"]

        # Fetch live OI + LTP from Kiteconnect quote API
        trading_symbols = [f"NFO:{ts}" for ts in sym_lookup.values()]
        ts_to_quote: dict[str, dict] = {}
        try:
            if trading_symbols:
                raw_quotes = kite.quote(trading_symbols[:200])
                for k, v in raw_quotes.items():
                    ts_to_quote[k.split(":", 1)[-1]] = v
        except Exception:
            pass

        top_strikes = []
        total_ce_oi = 0
        total_pe_oi = 0
        for k in selected:
            ce_ts = sym_lookup.get((k, "CE"), "")
            pe_ts = sym_lookup.get((k, "PE"), "")
            ce_q  = ts_to_quote.get(ce_ts, {})
            pe_q  = ts_to_quote.get(pe_ts, {})

            ce_oi  = ce_q.get("oi", 0)
            pe_oi  = pe_q.get("oi", 0)
            ce_ltp = ce_q.get("last_price") or (round(_bs_price(spot, k, T, sigma, option_type="call"), 2) if spot > 0 else 0)
            pe_ltp = pe_q.get("last_price") or (round(_bs_price(spot, k, T, sigma, option_type="put"), 2) if spot > 0 else 0)

            total_ce_oi += ce_oi
            total_pe_oi += pe_oi
            top_strikes.append({
                "strike": k,
                "ce_oi": ce_oi, "ce_ltp": ce_ltp, "ce_iv": round(sigma * 100, 2),
                "pe_oi": pe_oi, "pe_ltp": pe_ltp, "pe_iv": round(sigma * 100, 2),
            })

        pcr = round(total_pe_oi / total_ce_oi, 2) if total_ce_oi else 0
        has_live_oi = total_ce_oi > 0 or total_pe_oi > 0

        return {
            "symbol": kite_name,
            "underlying": round(spot, 2),
            "expiry": expiry_strs,
            "pcr": pcr,
            "max_pain": 0.0,
            "total_ce_oi": total_ce_oi,
            "total_pe_oi": total_pe_oi,
            "top_strikes": top_strikes,
            "is_theoretical": not has_live_oi,
            "vix": round(vix, 2),
            "dte": dte,
        }

    try:
        return await loop.run_in_executor(None, _build)
    except Exception as e:
        return {"error": str(e)}


async def _kite_futures_strip(symbol: str) -> list[dict[str, Any]]:
    """Fallback: near/mid/far futures from Kiteconnect quotes, then yfinance if Kite unavailable."""
    loop = asyncio.get_event_loop()

    def _build() -> list[dict[str, Any]]:
        from backend.models.config import load_config
        cfg = load_config()
        if not cfg.zerodha.api_key or not cfg.zerodha.access_token:
            return _yfinance_futures_stub(symbol)

        from kiteconnect import KiteConnect
        kite = KiteConnect(api_key=cfg.zerodha.api_key)
        kite.set_access_token(cfg.zerodha.access_token)

        sym_map = {"BANKNIFTY": "BANKNIFTY", "FINNIFTY": "FINNIFTY", "MIDCPNIFTY": "MIDCPNIFTY"}
        kite_name = sym_map.get(symbol.upper(), "NIFTY")

        try:
            instruments = kite.instruments("NFO")
        except Exception:
            return _yfinance_futures_stub(symbol)

        futures = sorted(
            [i for i in instruments if i["name"] == kite_name and i["instrument_type"] == "FUT"],
            key=lambda x: x["expiry"],
        )[:3]
        if not futures:
            return _yfinance_futures_stub(symbol)

        trading_symbols = [f"NFO:{i['tradingsymbol']}" for i in futures]
        try:
            quotes = kite.quote(trading_symbols)
        except Exception:
            # Kiteconnect market data not available (token expired / insufficient permissions)
            return _yfinance_futures_stub(symbol, futures)

        result = []
        for fut in futures:
            key = f"NFO:{fut['tradingsymbol']}"
            q = quotes.get(key, {})
            ltp = q.get("last_price", 0)
            close = (q.get("ohlc") or {}).get("close", ltp) or ltp
            change_pct = round((ltp - close) / close * 100, 2) if close else 0
            result.append({
                "expiry": str(fut["expiry"]),
                "ltp": round(ltp, 2),
                "change_pct": change_pct,
                "oi": q.get("oi", 0),
            })

        # If all LTPs are 0, use yfinance spot as approximate
        if result and all(r["ltp"] == 0 for r in result):
            return _yfinance_futures_stub(symbol, futures)
        return result

    try:
        return await loop.run_in_executor(None, _build)
    except Exception:
        return []


def _yfinance_futures_stub(symbol: str, instruments: list | None = None) -> list[dict[str, Any]]:
    """Build a futures stub using yfinance spot price when live futures data is unavailable."""
    import yfinance as yf
    yf_map = {"NIFTY": "^NSEI", "BANKNIFTY": "^NSEBANK", "FINNIFTY": "NIFTY_FIN_SERVICE.NS"}
    try:
        spot = float(yf.Ticker(yf_map.get(symbol.upper(), "^NSEI")).fast_info.last_price or 0)
    except Exception:
        spot = 0.0
    if spot <= 0:
        return []

    # Approximate futures with spot (no carry cost model — just shows underlying price)
    if instruments:
        return [{"expiry": str(i["expiry"]), "ltp": round(spot, 2), "change_pct": 0.0, "oi": 0}
                for i in instruments[:3]]
    return [{"expiry": "—", "ltp": round(spot, 2), "change_pct": 0.0, "oi": 0}]


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
    result = [
        {
            "expiry": f.get("metadata", {}).get("expiryDate"),
            # lastPrice is the futures contract LTP; underlyingValue is the spot — never use spot as LTP
            "ltp": f.get("metadata", {}).get("lastPrice") or f.get("underlyingValue"),
            "change_pct": f.get("metadata", {}).get("pChange"),
            "oi": f.get("marketDeptOrderBook", {}).get("totalSellQuantity"),
        }
        for f in futures[:3]
    ]
    if result:
        return result
    # NSE blocked — fall back to Kiteconnect
    return await _kite_futures_strip(symbol)


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
