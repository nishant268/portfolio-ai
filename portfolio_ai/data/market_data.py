from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pandas as pd
import yfinance as yf


def get_price_history(ticker: str, days: int = 90) -> pd.DataFrame:
    end = date.today()
    start = end - timedelta(days=days)
    df = yf.download(ticker, start=start, end=end, progress=False)
    return df


def get_fundamentals(ticker: str) -> dict[str, Any]:
    info = yf.Ticker(ticker).info
    return {
        "pe_ratio": info.get("trailingPE"),
        "forward_pe": info.get("forwardPE"),
        "peg_ratio": info.get("pegRatio"),
        "price_to_book": info.get("priceToBook"),
        "debt_to_equity": info.get("debtToEquity"),
        "roe": info.get("returnOnEquity"),
        "revenue_growth": info.get("revenueGrowth"),
        "earnings_growth": info.get("earningsGrowth"),
        "profit_margin": info.get("profitMargins"),
        "market_cap": info.get("marketCap"),
        "52w_high": info.get("fiftyTwoWeekHigh"),
        "52w_low": info.get("fiftyTwoWeekLow"),
        "analyst_target": info.get("targetMeanPrice"),
        "recommendation": info.get("recommendationKey"),
        "short_ratio": info.get("shortRatio"),
    }


def compute_technicals(ticker: str) -> dict[str, float | str]:
    try:
        import ta
    except ImportError:
        return {"error": "pip install ta"}

    df = get_price_history(ticker, days=200)
    if df.empty:
        return {"error": "no price data"}

    close = df["Close"].squeeze()

    rsi = ta.momentum.RSIIndicator(close, window=14).rsi().iloc[-1]
    macd_obj = ta.trend.MACD(close)
    macd = macd_obj.macd().iloc[-1]
    macd_signal = macd_obj.macd_signal().iloc[-1]
    bb = ta.volatility.BollingerBands(close, window=20)
    bb_pct = bb.bollinger_pband().iloc[-1]
    sma_50 = close.rolling(50).mean().iloc[-1]
    sma_200 = close.rolling(200).mean().iloc[-1]
    current = float(close.iloc[-1])

    return {
        "rsi_14": round(float(rsi), 2),
        "macd": round(float(macd), 4),
        "macd_signal": round(float(macd_signal), 4),
        "macd_histogram": round(float(macd - macd_signal), 4),
        "bb_pct_b": round(float(bb_pct), 4),
        "sma_50": round(float(sma_50), 2),
        "sma_200": round(float(sma_200), 2),
        "price_vs_sma50": round((current / float(sma_50) - 1) * 100, 2),
        "price_vs_sma200": round((current / float(sma_200) - 1) * 100, 2),
        "golden_cross": "yes" if sma_50 > sma_200 else "no",
    }


def get_news_headlines(ticker: str, max_items: int = 10) -> list[str]:
    try:
        news = yf.Ticker(ticker).news or []
        return [item.get("title", "") for item in news[:max_items]]
    except Exception:
        return []
