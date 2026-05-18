from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.models.config import AppConfig, ZerodhaConfig, InvestorProfile, load_config, save_config

router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("/")
async def get_config():
    cfg = load_config()
    safe = cfg.model_dump()
    # Mask secrets
    if safe["zerodha"]["api_secret"]:
        safe["zerodha"]["api_secret"] = "****"
    if safe["zerodha"]["access_token"]:
        safe["zerodha"]["access_token"] = safe["zerodha"]["access_token"][:8] + "****"
    # Show whether LLM key is set (masked), not the value
    safe["llm_key_saved"] = bool(cfg.llm_api_key)
    safe["llm_api_key"] = ""   # never send key to frontend
    return safe


@router.post("/zerodha")
async def save_zerodha(payload: ZerodhaConfig):
    cfg = load_config()
    cfg.zerodha = payload
    cfg.configured = bool(payload.api_key and payload.access_token)
    save_config(cfg)
    return {"ok": True, "configured": cfg.configured}


@router.post("/zerodha/login-url")
async def get_login_url():
    cfg = load_config()
    if not cfg.zerodha.api_key:
        raise HTTPException(400, "API key not set")
    url = f"https://kite.zerodha.com/connect/login?api_key={cfg.zerodha.api_key}&v=3"
    return {"login_url": url}


@router.post("/zerodha/generate-token")
async def generate_token(payload: dict[str, str]):
    import asyncio
    cfg = load_config()
    request_token = payload.get("request_token", "").strip()
    if not request_token:
        raise HTTPException(400, "request_token required")
    if not cfg.zerodha.api_key:
        raise HTTPException(400, "API key not configured — save it in Setup first")
    if not cfg.zerodha.api_secret:
        raise HTTPException(400, "API secret not configured — save it in Setup first")
    try:
        from kiteconnect import KiteConnect

        def _exchange():
            kite = KiteConnect(api_key=cfg.zerodha.api_key)
            return kite.generate_session(request_token, api_secret=cfg.zerodha.api_secret)

        # Run the blocking kiteconnect call in a thread so the event loop stays free
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, _exchange)

        cfg.zerodha.access_token = data["access_token"]
        cfg.zerodha.user_id = data.get("user_id", "")
        cfg.configured = True
        save_config(cfg)
        return {"ok": True, "user_id": cfg.zerodha.user_id}
    except Exception as exc:
        raise HTTPException(500, str(exc))


@router.post("/profile")
async def save_profile(profile: InvestorProfile):
    cfg = load_config()
    cfg.profile = profile
    save_config(cfg)
    return {"ok": True}


@router.post("/llm")
async def save_llm(payload: dict[str, str]):
    cfg = load_config()
    cfg.llm_provider = payload.get("provider", "openai")
    cfg.llm_model = payload.get("model") or None
    cfg.llm_api_key = payload.get("api_key", "")
    save_config(cfg)
    return {"ok": True}


@router.get("/llm-test")
async def test_llm():
    """
    Validates the API key WITHOUT making an LLM call.
    - Checks key format (saves quota)
    - For Gemini: calls the free /models list endpoint (zero token cost)
    - For OpenAI/Anthropic: validates key via models list (free endpoint)
    - For Ollama: just checks if the service is running
    """
    import httpx, re
    cfg = load_config()
    provider = cfg.llm_provider
    key = cfg.llm_api_key

    if not key and provider != "ollama":
        return {"ok": False, "error": f"No API key saved for {provider}. Go to Setup → Step 3 and paste your key."}

    try:
        # ── Google Gemini: list models (FREE, no tokens used) ─────────────────
        if provider == "google":
            if not key.startswith("AIza"):
                return {"ok": False, "error": "Invalid Gemini key format. Should start with 'AIza'."}
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(
                    f"https://generativelanguage.googleapis.com/v1beta/models?key={key}&pageSize=1"
                )
            if r.status_code == 400:
                return {"ok": False, "error": "Invalid API key. Check it in Google AI Studio."}
            if r.status_code == 403:
                return {"ok": False, "error": "API key unauthorised. Make sure Gemini API is enabled in your project."}
            if r.status_code == 200:
                model = cfg.llm_model or "gemini-2.0-flash-lite"
                return {"ok": True, "response": f"Key valid ✓ — using {model}", "provider": provider}
            return {"ok": False, "error": f"HTTP {r.status_code}: {r.text[:150]}"}

        # ── OpenAI / DeepSeek: list models (FREE) ─────────────────────────────
        if provider in ("openai", "deepseek"):
            base = "https://api.deepseek.com/v1" if provider == "deepseek" else "https://api.openai.com/v1"
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(
                    f"{base}/models",
                    headers={"Authorization": f"Bearer {key}"},
                )
            if r.status_code == 401:
                return {"ok": False, "error": "Invalid API key. Check it in your OpenAI dashboard."}
            if r.status_code == 200:
                model = cfg.llm_model or "gpt-4o-mini"
                return {"ok": True, "response": f"Key valid ✓ — using {model}", "provider": provider}
            return {"ok": False, "error": f"HTTP {r.status_code}: {r.text[:150]}"}

        # ── Anthropic: validate key header (FREE — returns 200 or 401) ─────────
        if provider == "anthropic":
            # Anthropic has no public models list endpoint, but /v1/models returns 200 if key is valid
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(
                    "https://api.anthropic.com/v1/models",
                    headers={"x-api-key": key, "anthropic-version": "2023-06-01"},
                )
            if r.status_code == 401:
                return {"ok": False, "error": "Invalid Anthropic API key."}
            if r.status_code == 200:
                model = cfg.llm_model or "claude-haiku-4-5-20251001"
                return {"ok": True, "response": f"Key valid ✓ — using {model}", "provider": provider}
            return {"ok": False, "error": f"HTTP {r.status_code}: {r.text[:150]}"}

        # ── Ollama: check service is running (FREE) ────────────────────────────
        if provider == "ollama":
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.get("http://localhost:11434/api/tags")
            models = [m["name"] for m in r.json().get("models", [])]
            if not models:
                return {"ok": False, "error": "Ollama running but no models pulled. Run: ollama pull llama3.1:8b"}
            return {"ok": True, "response": f"Ollama running ✓ — {len(models)} model(s): {', '.join(models[:3])}", "provider": provider}

        return {"ok": False, "error": f"Unknown provider: {provider}"}

    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.post("/mode")
async def save_mode(payload: dict[str, str]):
    cfg = load_config()
    m = payload.get("mode", "investor")
    if m not in ("investor", "trader"):
        raise HTTPException(400, "mode must be investor or trader")
    cfg.mode = m  # type: ignore[assignment]
    save_config(cfg)
    return {"ok": True, "mode": m}
