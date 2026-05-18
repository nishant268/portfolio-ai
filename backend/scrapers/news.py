"""
Financial news aggregator — scrapes RSS feeds from ET, Mint, Business Standard.
"""
from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime
from typing import Any

import feedparser
import httpx

_FEEDS = [
    # ── Indian Markets ─────────────────────────────────────────────────────────
    {"source": "Economic Times",    "url": "https://economictimes.indiatimes.com/markets/stocks/rss.cms",          "category": "stocks"},
    {"source": "Economic Times",    "url": "https://economictimes.indiatimes.com/markets/rss.cms",                 "category": "markets"},
    {"source": "Economic Times",    "url": "https://economictimes.indiatimes.com/markets/commodities/rss.cms",     "category": "commodities"},
    {"source": "LiveMint",          "url": "https://www.livemint.com/rss/markets",                                 "category": "markets"},
    {"source": "LiveMint",          "url": "https://www.livemint.com/rss/companies",                               "category": "companies"},
    {"source": "Business Standard", "url": "https://www.business-standard.com/rss/markets-106.rss",               "category": "markets"},
    {"source": "Business Standard", "url": "https://www.business-standard.com/rss/finance-109.rss",               "category": "finance"},
    {"source": "Moneycontrol",      "url": "https://www.moneycontrol.com/rss/business.xml",                       "category": "business"},
    {"source": "Moneycontrol",      "url": "https://www.moneycontrol.com/rss/marketreports.xml",                  "category": "markets"},
    {"source": "Financial Express", "url": "https://www.financialexpress.com/market/feed/",                       "category": "markets"},
    {"source": "NDTV Profit",       "url": "https://feeds.feedburner.com/ndtvprofit-latest",                      "category": "markets"},
    {"source": "Zee Business",      "url": "https://www.zeebiz.com/rss/markets.xml",                              "category": "markets"},
    # ── Global / Macro ─────────────────────────────────────────────────────────
    {"source": "Reuters India",     "url": "https://feeds.reuters.com/reuters/INbusinessNews",                    "category": "global"},
    {"source": "Reuters Markets",   "url": "https://feeds.reuters.com/reuters/businessNews",                      "category": "global"},
    {"source": "Bloomberg",         "url": "https://feeds.bloomberg.com/markets/news.rss",                        "category": "global"},
    {"source": "CNBC",              "url": "https://www.cnbc.com/id/10000664/device/rss/rss.html",                "category": "global"},
]

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; PortfolioAI/1.0; +https://github.com)"
}


async def _fetch_feed(session: httpx.AsyncClient, feed_meta: dict[str, str]) -> list[dict[str, Any]]:
    try:
        resp = await session.get(feed_meta["url"], timeout=10)
        parsed = feedparser.parse(resp.text)
        items = []
        for entry in parsed.entries[:8]:
            uid = hashlib.md5(entry.get("link", entry.get("title", "")).encode()).hexdigest()[:12]
            pub = entry.get("published", entry.get("updated", ""))
            try:
                pub_dt = datetime(*entry.published_parsed[:6]).isoformat() if entry.get("published_parsed") else pub
            except Exception:
                pub_dt = pub

            items.append({
                "id": uid,
                "title": entry.get("title", "").strip(),
                "summary": entry.get("summary", "")[:300].strip(),
                "url": entry.get("link", ""),
                "source": feed_meta["source"],
                "category": feed_meta["category"],
                "published_at": pub_dt,
            })
        return items
    except Exception as exc:
        return []


async def fetch_all_news(max_per_feed: int = 8) -> list[dict[str, Any]]:
    async with httpx.AsyncClient(headers=_HEADERS, follow_redirects=True) as session:
        tasks = [_fetch_feed(session, feed) for feed in _FEEDS]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    seen: set[str] = set()
    news: list[dict[str, Any]] = []
    for batch in results:
        if isinstance(batch, list):
            for item in batch:
                if item["title"] and item["id"] not in seen:
                    seen.add(item["id"])
                    news.append(item)

    # Sort by published_at descending (best-effort)
    news.sort(key=lambda x: x.get("published_at", ""), reverse=True)
    return news[:80]


async def fetch_news_for_ticker(ticker: str) -> list[dict[str, Any]]:
    """Filter cached news for mentions of a ticker or company name."""
    all_news = await fetch_all_news()
    term = ticker.upper()
    return [
        n for n in all_news
        if term in n["title"].upper() or term in n["summary"].upper()
    ]
