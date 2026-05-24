"""
Auto-trading scheduler.
Runs the rule-based paper trading session every 60 seconds during NSE market hours.
Zero LLM/Claude calls — purely rule-based for automation.
Claude is only called when user explicitly requests it for real orders.
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

_MARKET_OPEN_H, _MARKET_OPEN_M   = 9,  15
_MARKET_CLOSE_H, _MARKET_CLOSE_M = 15, 30


def _ist_now() -> datetime:
    """Current time in IST (UTC+5:30)."""
    from datetime import timezone, timedelta
    return datetime.now(timezone(timedelta(hours=5, minutes=30)))


def is_market_open() -> bool:
    """True during NSE trading hours: Mon–Fri 9:15–15:30 IST."""
    now = _ist_now()
    if now.weekday() >= 5:           # Saturday / Sunday
        return False
    open_min  = _MARKET_OPEN_H  * 60 + _MARKET_OPEN_M
    close_min = _MARKET_CLOSE_H * 60 + _MARKET_CLOSE_M
    cur_min   = now.hour * 60 + now.minute
    return open_min <= cur_min <= close_min


def seconds_to_market_open() -> int:
    """Seconds until next market open (returns 0 if market already open)."""
    now = _ist_now()
    if is_market_open():
        return 0
    # Find next weekday 9:15 IST
    from datetime import timedelta
    day = now
    for _ in range(8):
        day = day + timedelta(days=1)
        if day.weekday() < 5:
            target = day.replace(hour=9, minute=15, second=0, microsecond=0)
            delta = (target - now).total_seconds()
            return int(max(delta, 0))
    return 86400


class AutoTraderStatus:
    def __init__(self) -> None:
        self.running       = False
        self.mode          = "investor"
        self.interval      = 60          # seconds between sessions
        self.run_count     = 0
        self.last_run_at: str | None = None
        self.next_run_in   = 0           # seconds
        self.last_result: dict[str, Any] = {}
        self.recent_trades: list[dict[str, Any]] = []   # last 20 trades
        self.error: str | None = None
        self._task: asyncio.Task | None = None

    def to_dict(self) -> dict[str, Any]:
        ist = _ist_now()
        return {
            "running":       self.running,
            "mode":          self.mode,
            "interval":      self.interval,
            "run_count":     self.run_count,
            "last_run_at":   self.last_run_at,
            "next_run_in":   self.next_run_in,
            "market_open":   is_market_open(),
            "ist_time":      ist.strftime("%H:%M:%S IST"),
            "last_result":   self.last_result,
            "recent_trades": self.recent_trades[-10:],
            "error":         self.error,
        }


_status = AutoTraderStatus()


def get_status() -> AutoTraderStatus:
    return _status


async def _run_loop(mode: str, interval: int) -> None:
    from backend.agents.paper_trader import run_trading_session
    from backend.models.config import load_config
    import time

    _status.running  = True
    _status.mode     = mode
    _status.interval = interval
    _status.error    = None

    while _status.running:
        cycle_start = time.monotonic()
        try:
            if is_market_open():
                cfg = load_config()
                _status.last_result = {"status": "analyzing", "mode": mode}
                result = await run_trading_session(
                    mode=mode,
                    initial_capital=1_000_000.0,
                )
                _status.run_count += 1
                _status.last_run_at = datetime.utcnow().isoformat()
                _status.last_result = result
                _status.error = None

                # Keep a rolling list of trades for the live feed
                for t in result.get("executed_trades", []):
                    _status.recent_trades.append({
                        **t,
                        "ran_at": _status.last_run_at,
                        "run_no": _status.run_count,
                    })
                _status.recent_trades = _status.recent_trades[-50:]  # last 50

            else:
                _status.last_result = {
                    "status": "market_closed",
                    "message": f"Market closed. Next open in ~{seconds_to_market_open() // 60} min.",
                }

        except asyncio.CancelledError:
            break
        except Exception as exc:
            _status.error = str(exc)[:200]

        # Strict cadence: target every `interval` seconds wall-clock, regardless
        # of how long the session took. If a session ran 8s, sleep 52s; if it
        # ran 65s, fire immediately.
        elapsed = time.monotonic() - cycle_start
        remaining_total = max(int(interval - elapsed), 0)
        for remaining in range(remaining_total, 0, -1):
            if not _status.running:
                break
            _status.next_run_in = remaining
            await asyncio.sleep(1)

    _status.running     = False
    _status.next_run_in = 0


def start(mode: str = "investor", interval: int = 60) -> bool:
    if _status._task and not _status._task.done():
        return False   # already running
    loop = asyncio.get_event_loop()
    _status._task = loop.create_task(_run_loop(mode, interval))
    return True


def stop() -> bool:
    _status.running = False
    if _status._task:
        _status._task.cancel()
    return True
