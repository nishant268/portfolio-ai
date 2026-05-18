from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from backend.models.config import load_config
from backend.scrapers.nse import nse
from portfolio_ai.models.portfolio import Portfolio, Position, AssetClass

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


def _get_kite():
    cfg = load_config()
    if not cfg.zerodha.api_key or not cfg.zerodha.access_token:
        raise HTTPException(status_code=401, detail="Zerodha not configured. Visit /setup first.")
    try:
        from kiteconnect import KiteConnect
        kite = KiteConnect(api_key=cfg.zerodha.api_key)
        kite.set_access_token(cfg.zerodha.access_token)
        return kite
    except ImportError:
        raise HTTPException(status_code=500, detail="kiteconnect not installed")


@router.get("/")
async def get_portfolio() -> dict[str, Any]:
    kite = _get_kite()
    holdings = kite.holdings()
    margins = kite.margins()

    # Enrich with live NSE prices
    symbols = [h["tradingsymbol"] for h in holdings if h["quantity"] > 0]
    live_quotes: dict[str, dict] = {}
    if symbols:
        live_quotes = await nse.bulk_quotes(symbols)

    positions = []
    for h in holdings:
        if h["quantity"] <= 0:
            continue
        sym = h["tradingsymbol"]
        nse_data = live_quotes.get(sym, {})
        live_price = (
            nse_data.get("priceInfo", {}).get("lastPrice")
            or nse_data.get("lastPrice")
            or h["last_price"]
            or h["average_price"]
        )
        positions.append({
            "ticker": sym,
            "quantity": h["quantity"],
            "avg_cost": h["average_price"],
            "current_price": float(live_price),
            "broker": "zerodha",
            "isin": h.get("isin", ""),
            "market_value": float(live_price) * h["quantity"],
            "cost_basis": h["average_price"] * h["quantity"],
            "unrealized_pnl": (float(live_price) - h["average_price"]) * h["quantity"],
            "unrealized_pnl_pct": ((float(live_price) - h["average_price"]) / h["average_price"] * 100) if h["average_price"] else 0,
            "day_change_pct": nse_data.get("priceInfo", {}).get("pChange", 0),
        })

    cash = float(margins.get("equity", {}).get("available", {}).get("cash", 0))
    total_value = sum(p["market_value"] for p in positions) + cash
    total_cost = sum(p["cost_basis"] for p in positions)

    return {
        "positions": positions,
        "cash": cash,
        "total_value": total_value,
        "total_cost_basis": total_cost,
        "total_unrealized_pnl": total_value - cash - total_cost,
        "total_pnl_pct": ((total_value - cash - total_cost) / total_cost * 100) if total_cost else 0,
        "position_count": len(positions),
    }


@router.post("/orders/sell")
async def place_sell_order(payload: dict[str, Any]):
    kite = _get_kite()
    cfg = load_config()

    if not cfg.profile.auto_sell_enabled and not payload.get("confirmed"):
        raise HTTPException(status_code=403, detail="Auto-sell disabled. Pass confirmed=true to proceed.")

    from kiteconnect import KiteConnect
    order_id = kite.place_order(
        variety=KiteConnect.VARIETY_REGULAR,
        exchange=KiteConnect.EXCHANGE_NSE,
        tradingsymbol=payload["ticker"],
        transaction_type=KiteConnect.TRANSACTION_TYPE_SELL,
        quantity=int(payload["quantity"]),
        order_type=KiteConnect.ORDER_TYPE_MARKET if payload.get("order_type", "market") == "market" else KiteConnect.ORDER_TYPE_LIMIT,
        product=KiteConnect.PRODUCT_CNC,
        price=payload.get("limit_price"),
    )
    return {"order_id": order_id, "status": "submitted", "ticker": payload["ticker"]}


@router.post("/orders/postback")
async def order_postback(payload: dict[str, Any]):
    """
    Zerodha Postback URL endpoint.
    Zerodha POSTs order status updates here after every order state change.
    Log them — extend this to trigger alerts, auto-rebalance, etc.
    """
    import logging
    logging.getLogger("portfolio_ai.postback").info("Postback: %s", payload)
    return {"ok": True}


@router.get("/orders")
async def get_orders():
    kite = _get_kite()
    return {"orders": kite.orders()}
