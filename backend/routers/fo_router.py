from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.scrapers.nse_fo import fii_dii_data, fo_market_watch, futures_strip, option_chain

router = APIRouter(prefix="/api/fo", tags=["f&o"])


@router.get("/option-chain/{symbol}")
async def get_option_chain(symbol: str):
    data = await option_chain(symbol)
    if "error" in data:
        raise HTTPException(502, data["error"])
    return data


@router.get("/futures/{symbol}")
async def get_futures(symbol: str = "NIFTY"):
    return {"data": await futures_strip(symbol)}


@router.get("/fii-dii")
async def get_fii_dii():
    return await fii_dii_data()


@router.get("/fo-positions")
async def get_fo_positions():
    """Fetch live F&O positions from Zerodha."""
    from backend.models.config import load_config
    cfg = load_config()
    if not cfg.zerodha.access_token:
        raise HTTPException(401, "Zerodha not configured")
    try:
        from kiteconnect import KiteConnect
        kite = KiteConnect(api_key=cfg.zerodha.api_key)
        kite.set_access_token(cfg.zerodha.access_token)
        positions = kite.positions()
        fo = [
            p for p in (positions.get("net", []) + positions.get("day", []))
            if p.get("product") in ("NRML", "MIS") and p.get("quantity", 0) != 0
        ]
        return {"positions": fo}
    except Exception as e:
        raise HTTPException(500, str(e))
