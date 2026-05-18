"""
FastAPI backend for Portfolio AI Dashboard.
Run: uvicorn backend.main:app --reload --port 8000
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from backend.routers.market import router as market_router
from backend.routers.news_router import router as news_router
from backend.routers.portfolio_router import router as portfolio_router
from backend.routers.config_router import router as config_router
from backend.routers.analysis_router import router as analysis_router
from backend.routers.chat_router import router as chat_router
from backend.routers.fo_router import router as fo_router
from backend.routers.paper_router import router as paper_router
from backend.routers.agent_stream_router import router as agent_stream_router
from backend.models.chat import init_db
from backend.models.paper_trade import init_db as init_paper_db
from backend.scrapers.nse import nse
import backend.agents.auto_trader as auto_trader_mod

app = FastAPI(title="Portfolio AI", version="1.0.0")

import os as _os

_FRONTEND_URL = _os.environ.get("FRONTEND_URL", "")
_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
if _FRONTEND_URL:
    _ORIGINS.append(_FRONTEND_URL)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ORIGINS,
    allow_origin_regex=r"https://.*\.onrender\.com",   # all Render subdomains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()         # create chat.db tables on startup
init_paper_db()   # create paper_trade.db tables


@app.on_event("startup")
async def startup():
    """Auto-start the paper trading scheduler on server start."""
    from backend.models.config import load_config
    cfg = load_config()
    mode = cfg.mode if hasattr(cfg, "mode") else "investor"
    auto_trader_mod.start(mode=mode, interval=60)

app.include_router(market_router)
app.include_router(news_router)
app.include_router(portfolio_router)
app.include_router(config_router)
app.include_router(analysis_router)
app.include_router(chat_router)
app.include_router(fo_router)
app.include_router(paper_router)
app.include_router(agent_stream_router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "portfolio-ai"}


# ── WebSocket: live market ticker ─────────────────────────────────────────────

class ConnectionManager:
    def __init__(self) -> None:
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self.active.remove(ws)

    async def broadcast(self, data: dict[str, Any]) -> None:
        dead = []
        for ws in self.active:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.active.remove(ws)


manager = ConnectionManager()


@app.websocket("/ws/market")
async def market_ws(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            indices = await nse.all_indices()
            key_indices = [i for i in indices if i.get("indexSymbol") in
                           ["NIFTY 50", "NIFTY BANK", "NIFTY IT", "INDIA VIX"]]
            await websocket.send_json({"type": "indices", "data": key_indices})
            await asyncio.sleep(15)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)


# ── WebSocket: live auto-trader feed ─────────────────────────────────────────

@app.websocket("/ws/auto-trader")
async def auto_trader_ws(websocket: WebSocket):
    """Streams auto-trader status + new trades every 5 seconds."""
    await websocket.accept()
    seen_count = 0
    try:
        while True:
            st = auto_trader_mod.get_status()
            payload = st.to_dict()
            # Only send new_trades flag if run_count changed
            payload["has_new_trades"] = st.run_count != seen_count
            if st.run_count != seen_count:
                seen_count = st.run_count
            await websocket.send_json(payload)
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass


# ── Auto-trader REST control ──────────────────────────────────────────────────

@app.get("/api/auto-trader/status")
async def auto_trader_status():
    return auto_trader_mod.get_status().to_dict()


@app.post("/api/auto-trader/start")
async def auto_trader_start(mode: str = "investor", interval: int = 60):
    started = auto_trader_mod.start(mode=mode, interval=interval)
    return {"ok": True, "started": started, "mode": mode}


@app.post("/api/auto-trader/stop")
async def auto_trader_stop():
    auto_trader_mod.stop()
    return {"ok": True}
