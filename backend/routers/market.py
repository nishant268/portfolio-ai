from __future__ import annotations

from fastapi import APIRouter

from backend.scrapers.nse import nse

router = APIRouter(prefix="/api/market", tags=["market"])


@router.get("/status")
async def market_status():
    return await nse.market_status()


@router.get("/indices")
async def all_indices():
    data = await nse.all_indices()
    # Return key indices at top
    priority = ["NIFTY 50", "NIFTY BANK", "NIFTY IT", "NIFTY MIDCAP 100", "INDIA VIX"]
    ordered = sorted(
        data,
        key=lambda x: (priority.index(x.get("indexSymbol", "")) if x.get("indexSymbol") in priority else 99),
    )
    return {"indices": ordered}


@router.get("/nifty50")
async def nifty50():
    return await nse.nifty50_stocks()


@router.get("/quote/{symbol}")
async def quote(symbol: str):
    return await nse.quote(symbol)


@router.get("/gainers")
async def gainers():
    return {"data": await nse.gainers()}


@router.get("/losers")
async def losers():
    return {"data": await nse.losers()}


@router.get("/sectors")
async def sectors():
    return {"data": await nse.sector_performance()}
