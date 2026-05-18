"""
Simple in-memory TTL cache for LLM responses.
Identical inputs → return cached result, zero API call.
"""
from __future__ import annotations

import hashlib
import time
from typing import Any

_store: dict[str, tuple[float, Any]] = {}   # key → (expires_at, value)


def _key(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def get(raw: str) -> Any | None:
    k = _key(raw)
    if k in _store:
        expires, val = _store[k]
        if time.time() < expires:
            return val
        del _store[k]
    return None


def set(raw: str, value: Any, ttl_seconds: int = 1800) -> None:
    """Cache a response. Default TTL = 30 minutes."""
    _store[_key(raw)] = (time.time() + ttl_seconds, value)


def clear_expired() -> int:
    now = time.time()
    stale = [k for k, (exp, _) in _store.items() if exp < now]
    for k in stale:
        del _store[k]
    return len(stale)


def stats() -> dict[str, int]:
    now = time.time()
    return {
        "total": len(_store),
        "live": sum(1 for exp, _ in _store.values() if exp > now),
        "expired": sum(1 for exp, _ in _store.values() if exp <= now),
    }
