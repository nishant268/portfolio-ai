"""
NSE real-time data scraper.
Uses curl_cffi with Chrome impersonation to bypass Cloudflare protection.
Session is primed once by visiting the homepage to obtain cookies.
"""
from __future__ import annotations

import asyncio
from typing import Any

from curl_cffi import requests as cf_requests

_NSE = "https://www.nseindia.com"
_API_HEADERS = {
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Origin": "https://www.nseindia.com",
    "Referer": "https://www.nseindia.com/option-chain",
    "X-Requested-With": "XMLHttpRequest",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Dest": "empty",
    "Connection": "keep-alive",
}


_SESSION_TTL = 20 * 60   # re-prime cookies every 20 minutes


class NSEScraper:
    def __init__(self) -> None:
        self._session: cf_requests.Session | None = None
        self._lock = asyncio.Lock()
        self._session_born: float = 0.0

    def _make_session(self) -> cf_requests.Session:
        import time
        for attempt in range(3):
            try:
                session = cf_requests.Session(impersonate="chrome124")
                session.get(_NSE, timeout=20)                          # prime homepage cookies
                time.sleep(1.5)
                session.get(f"{_NSE}/option-chain", timeout=20)        # prime option-chain cookies
                self._session_born = time.time()
                return session
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(2)
        raise RuntimeError("Could not create NSE session")

    def _ensure_session(self) -> cf_requests.Session:
        import time
        if self._session is None or (time.time() - self._session_born) > _SESSION_TTL:
            self._session = self._make_session()
        return self._session

    def _get(self, path: str) -> dict[str, Any]:
        import time
        session = self._ensure_session()
        try:
            resp = session.get(f"{_NSE}{path}", headers=_API_HEADERS, timeout=15)
            if resp.status_code in (401, 403, 429):
                # Re-prime session and retry once
                self._session = self._make_session()
                time.sleep(1)
                resp = self._session.get(f"{_NSE}{path}", headers=_API_HEADERS, timeout=15)
            if resp.status_code != 200:
                return {"error": f"NSE returned HTTP {resp.status_code}"}
            return resp.json()
        except Exception as exc:
            self._session = None   # force re-prime on next call
            return {"error": str(exc)}

    # ── Async wrappers (run sync curl_cffi in thread pool) ────────────────────

    async def _aget(self, path: str) -> dict[str, Any]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._get, path)

    # ── Public API ────────────────────────────────────────────────────────────

    async def market_status(self) -> dict[str, Any]:
        return await self._aget("/api/marketStatus")

    async def all_indices(self) -> list[dict[str, Any]]:
        data = await self._aget("/api/allIndices")
        return data.get("data", [])

    async def nifty50_stocks(self) -> list[dict[str, Any]]:
        data = await self._aget("/api/equity-stockIndices?index=NIFTY%2050")
        return data.get("data", [])

    async def quote(self, symbol: str) -> dict[str, Any]:
        return await self._aget(f"/api/quote-equity?symbol={symbol.upper()}")

    async def gainers(self, count: int = 10) -> list[dict[str, Any]]:
        data = await self._aget("/api/live-analysis-variations?index=gainers&exchange=NSE")
        return data.get("NIFTY", {}).get("data", [])[:count]

    async def losers(self, count: int = 10) -> list[dict[str, Any]]:
        data = await self._aget("/api/live-analysis-variations?index=loosers&exchange=NSE")
        return data.get("NIFTY", {}).get("data", [])[:count]

    async def sector_performance(self) -> list[dict[str, Any]]:
        all_idx = await self.all_indices()
        sectors = [
            "NIFTY BANK", "NIFTY IT", "NIFTY PHARMA", "NIFTY AUTO",
            "NIFTY FMCG", "NIFTY METAL", "NIFTY ENERGY", "NIFTY REALTY",
            "NIFTY INFRA", "NIFTY MEDIA",
        ]
        return [i for i in all_idx if i.get("indexSymbol", "") in sectors]

    async def bulk_quotes(self, symbols: list[str]) -> dict[str, dict[str, Any]]:
        tasks = {sym: self.quote(sym) for sym in symbols}
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        return {
            sym: (r if isinstance(r, dict) else {})
            for sym, r in zip(tasks.keys(), results)
        }


nse = NSEScraper()
