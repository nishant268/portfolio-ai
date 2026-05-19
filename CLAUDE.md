# Portfolio AI — CLAUDE.md

Codebase guide for Claude Code. Read this before touching any file.

---

## Project Overview

Full-stack AI paper-trading dashboard for Indian markets (NSE/BSE).

- **Frontend**: Next.js 16 (App Router), React 19, TypeScript, Tailwind CSS 4, Recharts
- **Backend**: FastAPI (Python 3.11), SQLite via SQLModel, yfinance, curl_cffi
- **LLM**: Anthropic Claude / Google Gemini / OpenAI (user-configurable)
- **Market data**: NSE web scraper (`curl_cffi` Chrome impersonation) + yfinance

---

## Directory Map

```
portfolio-ai/
├── backend/
│   ├── main.py                   # FastAPI app, CORS, WebSockets, auto-trader startup
│   ├── agents/
│   │   ├── paper_trader.py       # Core trading session (rule engine + snapshot)
│   │   ├── rule_based_trader.py  # 5-analyst rule engine (zero LLM)
│   │   ├── trade_analyst.py      # Background Claude bull/bear/researcher analysis
│   │   └── auto_trader.py        # Scheduler: runs session every 60s during market hours
│   ├── routers/
│   │   ├── paper_router.py       # /api/paper/* — portfolio, trades, run, reset
│   │   ├── fo_router.py          # /api/fo/* — option chain, futures, FII/DII
│   │   ├── agent_stream_router.py# /api/agent-stream/* — SSE streaming pipeline
│   │   ├── analysis_router.py    # /api/analysis/* — quick/deep/portfolio-score
│   │   ├── portfolio_router.py   # /api/portfolio — Zerodha real portfolio
│   │   ├── market.py             # /api/market/* — indices, quotes, gainers
│   │   ├── chat_router.py        # /api/chat/* — sessions, messages
│   │   ├── config_router.py      # /api/config/* — Zerodha, profile, LLM setup
│   │   └── news_router.py        # /api/news/*
│   ├── scrapers/
│   │   ├── nse.py                # NSEScraper (curl_cffi Chrome impersonation)
│   │   └── nse_fo.py             # option_chain(), futures_strip(), fii_dii_data()
│   ├── models/
│   │   ├── paper_trade.py        # SQLModel schemas + all DB helpers
│   │   ├── config.py             # AppConfig (Zerodha, profile, LLM) → .portfolio_config.json
│   │   └── chat.py               # Chat session/message schemas
│   └── utils/
├── frontend/
│   ├── app/
│   │   ├── page.tsx              # Setup wizard (home)
│   │   ├── dashboard/page.tsx    # Real portfolio + Trader panel (option chain)
│   │   └── paper/page.tsx        # Paper trading — stats, chart, positions, trade history
│   ├── components/
│   │   ├── dashboard/
│   │   │   ├── TraderPanel.tsx   # Option chain + futures display (OptionChainCard)
│   │   │   ├── MarketHeader.tsx  # Top bar with live indices via WebSocket
│   │   │   └── ...
│   │   ├── paper/
│   │   │   └── AgentPipeline.tsx # TradingAgents-style SSE streaming UI
│   │   └── ui/
│   │       └── AnalyseButton.tsx # Triggers /api/agent-stream SSE pipeline
│   └── lib/
│       ├── api.ts                # Axios client — api.*, foApi.*, chatApi.*
│       └── types.ts              # TypeScript interfaces (Portfolio, OptionChain, …)
└── portfolio_ai/                 # Shared Python library (brokers, TA, fundamentals)
    ├── brokers/                  # Zerodha + Alpaca adapters
    └── data/market_data.py       # compute_technicals(), get_fundamentals()
```

---

## Running the App

### Backend
```bash
cd portfolio-ai
pip install -r requirements.txt
uvicorn backend.main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev        # http://localhost:3000
```

Set `NEXT_PUBLIC_API_URL=http://localhost:8000` (default) or via `.env.local`.

---

## Key Architecture Decisions

### Trading Flow
1. **Rule-based engine first** — 5 analysts (Technical, Fundamental, Momentum, Sentiment, Market) score each stock. Zero LLM calls. Runs every 60s during market hours.
2. **Async Claude analysis** — after each trade, `_analyse_trade()` fires a background task (`asyncio.create_task`) to generate bull/bear/researcher debate. Never blocks trade execution.
3. **Auto-trader** (`auto_trader.py`) — background asyncio loop started at server startup via `@app.on_event("startup")`.

### Data Flow
- **Live prices** → yfinance `fast_info.last_price` (always run via `loop.run_in_executor` — never call synchronously in async routes)
- **Option chain / futures** → NSE web scraper (`curl_cffi` Chrome impersonation). Session primed by visiting homepage + option-chain page to obtain cookies.
- **Technicals** → `portfolio_ai/data/market_data.py` → TA library (RSI, MACD, Bollinger Bands, SMA)
- **Fundamentals** → yfinance `.info` dict (PE, ROE, revenue_growth, etc.)

### State Management (Frontend)
- No Redux/Zustand — plain React hooks
- **WebSocket** `/ws/auto-trader` → updates auto-trader status every 5s; triggers `load()` when `has_new_trades=true`
- **WebSocket** `/ws/market` → live indices every 15s
- **Polling** every 30s for paper portfolio, 15s for real portfolio

---

## Database

SQLite files in project root (or `$DATA_DIR`):
- `paper_trade.db` — paper trading data
- `chat.db` — chat sessions

Key tables: `paperportfolio`, `paperposition`, `papertrade`, `paperdailysnapshot`, `papertradeanalysis`

All DB helpers are in `backend/models/paper_trade.py`. Use the helper functions — never write raw SQL.

---

## NSE Scraper Notes

The scraper (`nse.py`) uses `curl_cffi` with Chrome impersonation to bypass Cloudflare.

**Session priming** is critical:
1. Visit homepage (`https://www.nseindia.com`) — sets `nseappid` cookie
2. Visit `/option-chain` page — sets additional session cookies

Required headers: `Origin`, `Referer` (option-chain page), `X-Requested-With`, `Sec-Fetch-*`.

If NSE blocks requests, the session auto re-primes on 401/403/429. If the `filtered` section of the option chain response is missing CE/PE totals, the scraper falls back to computing OI directly from `records.data` for the nearest expiry.

---

## Common Pitfalls

1. **Never call `_get_live_price()` or other yfinance functions directly in an async route** — always use `await loop.run_in_executor(None, _get_live_price, ticker)`. Blocking the event loop causes silent timeouts → prices return 0 → P&L shows ₹0.

2. **Trade history limit** — default is 500 trades (`paper_router.py` + `page.tsx`). Don't lower it; SQLite handles it fine.

3. **Max pain calculation** — uses nearest expiry strikes only. Using all expiries mixes data from different contracts and gives wrong results.

4. **Claude analysis** — runs as a fire-and-forget background task. If LLM key is not configured or quota is exhausted, it fails silently (by design). Trade execution is never blocked.

5. **Mode switching** — "investor" and "trader" modes have separate portfolios in the DB. Switching mode in the UI calls `/api/auto-trader/start?mode=X` to restart the scheduler.

6. **CORS** — origins are whitelisted in `main.py`. For new deploy targets, add `FRONTEND_URL` env var.

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Backend base URL |
| `DATA_DIR` | project root | SQLite file location |
| `FRONTEND_URL` | — | Added to CORS allowlist on Render |
| `RENDER_EXTERNAL_URL` | — | Enables keep-alive pinger (Render only) |

LLM API keys are stored in `.portfolio_config.json` (via Setup UI), not env vars.

---

## Adding New Features

- **New API endpoint** → add router in `backend/routers/`, include it in `main.py`, add typed helper in `frontend/lib/api.ts`
- **New analyst** → add to `rule_based_trader.py`, wire up score in `make_final_decision()`, add to `_rule_based_decide()` in `paper_trader.py`
- **New watchlist stock** → add NSE ticker to `INVESTOR_WATCHLIST` or `TRADER_WATCHLIST` in `paper_trader.py`
- **New DB column** → add field to SQLModel class in `paper_trade.py`, delete `paper_trade.db` and restart (SQLite migrations not set up)
