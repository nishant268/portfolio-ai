from __future__ import annotations

import json
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field

import os as _os
_DATA_DIR = Path(_os.environ.get("DATA_DIR", Path(__file__).parent.parent.parent))
_DATA_DIR.mkdir(parents=True, exist_ok=True)
_CONFIG_PATH = _DATA_DIR / ".portfolio_config.json"


class ZerodhaConfig(BaseModel):
    api_key: str = ""
    api_secret: str = ""
    access_token: str = ""
    user_id: str = ""


class AllocationConfig(BaseModel):
    large_cap: float = 50.0
    mid_cap: float = 30.0
    small_cap: float = 10.0
    debt: float = 5.0
    cash: float = 5.0


class InvestorProfile(BaseModel):
    name: str = "Investor"
    risk_tolerance: Literal["conservative", "moderate", "aggressive"] = "moderate"
    investment_horizon: Literal["short", "medium", "long"] = "long"
    target_annual_return: float = 15.0          # percent
    stop_loss_pct: float = 8.0                  # auto stop-loss %
    take_profit_pct: float = 25.0               # take profit %
    rebalance_frequency: Literal["monthly", "quarterly", "annually"] = "quarterly"
    allocation: AllocationConfig = Field(default_factory=AllocationConfig)
    auto_sell_enabled: bool = False             # require human confirmation by default


class AppConfig(BaseModel):
    zerodha: ZerodhaConfig = Field(default_factory=ZerodhaConfig)
    profile: InvestorProfile = Field(default_factory=InvestorProfile)
    llm_provider: str = "openai"
    llm_model: Optional[str] = None
    llm_api_key: str = ""          # stored in config — no env var needed
    configured: bool = False
    mode: Literal["investor", "trader"] = "investor"


def load_config() -> AppConfig:
    cfg: AppConfig
    if _CONFIG_PATH.exists():
        try:
            cfg = AppConfig.model_validate_json(_CONFIG_PATH.read_text())
        except Exception:
            cfg = AppConfig()
    else:
        cfg = AppConfig()

    # Override with environment variables — works on Render where config
    # file may not persist across restarts (no persistent disk on free tier)
    if not cfg.zerodha.api_key:
        cfg.zerodha.api_key    = _os.environ.get("ZERODHA_API_KEY", "")
    if not cfg.zerodha.api_secret:
        cfg.zerodha.api_secret = _os.environ.get("ZERODHA_API_SECRET", "")
    if not cfg.zerodha.access_token:
        cfg.zerodha.access_token = _os.environ.get("ZERODHA_ACCESS_TOKEN", "")
    if not cfg.llm_api_key:
        cfg.llm_api_key = (
            _os.environ.get("ANTHROPIC_API_KEY")
            or _os.environ.get("GOOGLE_API_KEY")
            or _os.environ.get("OPENAI_API_KEY")
            or ""
        )
    if not cfg.llm_provider or cfg.llm_provider == "openai":
        if _os.environ.get("ANTHROPIC_API_KEY"):
            cfg.llm_provider = "anthropic"
            cfg.llm_model = cfg.llm_model or "claude-haiku-4-5-20251001"
        elif _os.environ.get("GOOGLE_API_KEY"):
            cfg.llm_provider = "google"
            cfg.llm_model = cfg.llm_model or "gemini-2.0-flash-lite"

    # Mark configured if Zerodha credentials are present from any source
    if cfg.zerodha.api_key and cfg.zerodha.access_token:
        cfg.configured = True

    return cfg


def save_config(cfg: AppConfig) -> None:
    _CONFIG_PATH.write_text(cfg.model_dump_json(indent=2))
