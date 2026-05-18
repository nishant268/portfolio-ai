from __future__ import annotations

from fastapi import APIRouter, Query

from backend.scrapers.news import fetch_all_news, fetch_news_for_ticker

router = APIRouter(prefix="/api/news", tags=["news"])


@router.get("/")
async def all_news(limit: int = Query(60, le=80)):
    news = await fetch_all_news()
    return {"articles": news[:limit]}


@router.get("/ticker/{symbol}")
async def ticker_news(symbol: str):
    news = await fetch_news_for_ticker(symbol)
    return {"articles": news, "ticker": symbol}
