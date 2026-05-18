"""
Multi-agent portfolio evaluator built on TradingAgents' LangGraph pattern.

Agent pipeline per position:
  FundamentalsAnalyst → TechnicalAnalyst → NewsAnalyst →
  BearishResearcher ⇄ BullishResearcher (debate) →
  RiskManager → PortfolioManager (approve/reject sell)
"""
from __future__ import annotations

import json
import os
from typing import Annotated, Any, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages

from portfolio_ai.data.market_data import compute_technicals, get_fundamentals, get_news_headlines
from portfolio_ai.models.portfolio import EvaluationResult, Position, SignalStrength

# ── LLM factory (mirrors TradingAgents pattern) ─────────────────────────────

def _make_llm(provider: str = "openai", model: str | None = None, temperature: float = 0.1, api_key: str | None = None):
    """
    Build an LLM client. api_key priority:
      1. Explicitly passed api_key arg  (from config file — user entered in Setup)
      2. Environment variable           (OPENAI_API_KEY / ANTHROPIC_API_KEY etc.)
    """
    key = api_key or None   # empty string → None so langchain falls back to env var

    if provider == "openai":
        from langchain_openai import ChatOpenAI
        kwargs = {"model": model or "gpt-4o-mini", "temperature": temperature}
        if key:
            kwargs["api_key"] = key
        return ChatOpenAI(**kwargs)
    elif provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        kwargs = {"model": model or "claude-sonnet-4-6", "temperature": temperature}
        if key:
            kwargs["api_key"] = key
        return ChatAnthropic(**kwargs)
    elif provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI
        kwargs = {"model": model or "gemini-2.0-flash-lite", "temperature": temperature}
        if key:
            kwargs["google_api_key"] = key
        return ChatGoogleGenerativeAI(**kwargs)
    elif provider == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(model=model or "llama3.1:8b", temperature=temperature)
    elif provider == "deepseek":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model or "deepseek-chat",
            api_key=key or os.environ.get("DEEPSEEK_API_KEY"),
            base_url="https://api.deepseek.com/v1",
            temperature=temperature,
        )
    raise ValueError(f"Unknown provider: {provider}")


# ── Graph state ──────────────────────────────────────────────────────────────

class EvalState(TypedDict):
    ticker: str
    position: dict[str, Any]
    fundamentals: dict[str, Any]
    technicals: dict[str, Any]
    news: list[str]
    fundamentals_report: str
    technical_report: str
    news_report: str
    bullish_case: str
    bearish_case: str
    risk_assessment: str
    final_decision: str
    signal: str
    confidence: float
    target_price: float | None
    stop_loss: float | None
    messages: Annotated[list, add_messages]


# ── Agent nodes ──────────────────────────────────────────────────────────────

def fundamentals_analyst(state: EvalState, llm) -> dict:
    f = state["fundamentals"]
    pos = state["position"]
    prompt = f"""You are a fundamentals analyst. Evaluate {state['ticker']} for a potential SELL decision.

Position context:
- Held qty: {pos['quantity']}, avg cost: ${pos['avg_cost']:.2f}, current: ${pos['current_price']:.2f}
- Unrealized P&L: {pos['unrealized_pnl_pct']:.1f}%

Fundamentals:
{json.dumps(f, indent=2)}

Write a concise 3-4 sentence assessment: Is the stock overvalued, fairly valued, or undervalued?
Flag any red flags (high debt, falling margins, negative growth).
End with: SIGNAL: [STRONG_SELL | SELL | HOLD | BUY | STRONG_BUY]"""

    resp = llm.invoke([HumanMessage(content=prompt)])
    return {"fundamentals_report": resp.content}


def technical_analyst(state: EvalState, llm) -> dict:
    t = state["technicals"]
    prompt = f"""You are a technical analyst. Evaluate {state['ticker']} charts.

Technical indicators:
{json.dumps(t, indent=2)}

Interpret RSI (>70 overbought, <30 oversold), MACD crossover, Bollinger Band position,
and 50/200-day SMA alignment. Write 3-4 sentences.
End with: SIGNAL: [STRONG_SELL | SELL | HOLD | BUY | STRONG_BUY]"""

    resp = llm.invoke([HumanMessage(content=prompt)])
    return {"technical_report": resp.content}


def news_analyst(state: EvalState, llm) -> dict:
    headlines = "\n".join(f"- {h}" for h in state["news"]) or "No recent news."
    prompt = f"""You are a news and sentiment analyst. Evaluate recent headlines for {state['ticker']}.

Headlines:
{headlines}

Assess the overall sentiment and any material events that could justify selling or holding.
Write 2-3 sentences. End with: SIGNAL: [STRONG_SELL | SELL | HOLD | BUY | STRONG_BUY]"""

    resp = llm.invoke([HumanMessage(content=prompt)])
    return {"news_report": resp.content}


def bullish_researcher(state: EvalState, llm) -> dict:
    prompt = f"""You are a bullish researcher. Build the strongest case for HOLDING or BUYING {state['ticker']}.

Fundamentals report: {state['fundamentals_report']}
Technical report: {state['technical_report']}
News report: {state['news_report']}

Counter any sell arguments. Focus on upside catalysts, undervaluation, or technical strength.
2-3 sentences."""

    resp = llm.invoke([HumanMessage(content=prompt)])
    return {"bullish_case": resp.content}


def bearish_researcher(state: EvalState, llm) -> dict:
    prompt = f"""You are a bearish researcher. Build the strongest case for SELLING {state['ticker']}.

Fundamentals report: {state['fundamentals_report']}
Technical report: {state['technical_report']}
News report: {state['news_report']}
Bullish case: {state.get('bullish_case', '')}

Counter the bull arguments. Focus on downside risks, overvaluation, or technical weakness.
2-3 sentences."""

    resp = llm.invoke([HumanMessage(content=prompt)])
    return {"bearish_case": resp.content}


def risk_manager(state: EvalState, llm) -> dict:
    pos = state["position"]
    prompt = f"""You are a risk manager. Assess portfolio risk for {state['ticker']}.

Position: qty={pos['quantity']}, unrealized P&L={pos['unrealized_pnl_pct']:.1f}%
Market value: ${pos['market_value']:.2f}

Bull case: {state['bullish_case']}
Bear case: {state['bearish_case']}

Evaluate: concentration risk, stop-loss levels, and downside protection needs.
Recommend a stop-loss price and target price if applicable.
Format your response as JSON:
{{"risk_score": <1-10>, "stop_loss": <price or null>, "target_price": <price or null>, "assessment": "<text>"}}"""

    resp = llm.invoke([HumanMessage(content=prompt)])
    try:
        data = json.loads(resp.content.strip().strip("```json").strip("```"))
    except Exception:
        data = {"risk_score": 5, "stop_loss": None, "target_price": None, "assessment": resp.content}

    return {
        "risk_assessment": data.get("assessment", ""),
        "stop_loss": data.get("stop_loss"),
        "target_price": data.get("target_price"),
    }


def portfolio_manager(state: EvalState, llm) -> dict:
    pos = state["position"]
    prompt = f"""You are the portfolio manager making the final SELL/HOLD decision for {state['ticker']}.

Position summary:
- Qty: {pos['quantity']}, Avg cost: ${pos['avg_cost']:.2f}, Current: ${pos['current_price']:.2f}
- Unrealized P&L: {pos['unrealized_pnl_pct']:.1f}%

Agent reports:
FUNDAMENTALS: {state['fundamentals_report']}
TECHNICAL: {state['technical_report']}
NEWS: {state['news_report']}
BULL CASE: {state['bullish_case']}
BEAR CASE: {state['bearish_case']}
RISK ASSESSMENT: {state['risk_assessment']}

Make a final decision. Respond as JSON:
{{"signal": "STRONG_SELL|SELL|HOLD|BUY|STRONG_BUY", "confidence": <0.0-1.0>, "action": "<what to do in plain English>"}}"""

    resp = llm.invoke([HumanMessage(content=prompt)])
    try:
        data = json.loads(resp.content.strip().strip("```json").strip("```"))
    except Exception:
        data = {"signal": "HOLD", "confidence": 0.5, "action": resp.content}

    return {
        "signal": data.get("signal", "HOLD"),
        "confidence": float(data.get("confidence", 0.5)),
        "final_decision": data.get("action", ""),
    }


# ── Graph builder ─────────────────────────────────────────────────────────────

def build_eval_graph(provider: str = "openai", model: str | None = None):
    from backend.models.config import load_config as _load_cfg
    _cfg = _load_cfg()
    _key = _cfg.llm_api_key or None
    llm_think = _make_llm(provider, model, temperature=0.1, api_key=_key)
    llm_debate = _make_llm(provider, model, temperature=0.3, api_key=_key)

    g = StateGraph(EvalState)

    g.add_node("fundamentals_analyst", lambda s: fundamentals_analyst(s, llm_think))
    g.add_node("technical_analyst", lambda s: technical_analyst(s, llm_think))
    g.add_node("news_analyst", lambda s: news_analyst(s, llm_think))
    g.add_node("bullish_researcher", lambda s: bullish_researcher(s, llm_debate))
    g.add_node("bearish_researcher", lambda s: bearish_researcher(s, llm_debate))
    g.add_node("risk_manager", lambda s: risk_manager(s, llm_think))
    g.add_node("portfolio_manager", lambda s: portfolio_manager(s, llm_think))

    # Analysts run in sequence (each builds on shared state)
    g.set_entry_point("fundamentals_analyst")
    g.add_edge("fundamentals_analyst", "technical_analyst")
    g.add_edge("technical_analyst", "news_analyst")
    g.add_edge("news_analyst", "bullish_researcher")
    g.add_edge("bullish_researcher", "bearish_researcher")
    g.add_edge("bearish_researcher", "risk_manager")
    g.add_edge("risk_manager", "portfolio_manager")
    g.add_edge("portfolio_manager", END)

    return g.compile()


# ── Public API ────────────────────────────────────────────────────────────────

async def evaluate_position(position: Position, provider: str = "openai", model: str | None = None) -> EvaluationResult:
    ticker = position.ticker

    fundamentals = get_fundamentals(ticker)
    technicals = compute_technicals(ticker)
    news = get_news_headlines(ticker)

    pos_dict = position.model_dump()
    pos_dict["unrealized_pnl_pct"] = position.unrealized_pnl_pct
    pos_dict["market_value"] = position.market_value

    graph = build_eval_graph(provider, model)

    initial_state: EvalState = {
        "ticker": ticker,
        "position": pos_dict,
        "fundamentals": fundamentals,
        "technicals": technicals,
        "news": news,
        "fundamentals_report": "",
        "technical_report": "",
        "news_report": "",
        "bullish_case": "",
        "bearish_case": "",
        "risk_assessment": "",
        "final_decision": "",
        "signal": "HOLD",
        "confidence": 0.5,
        "target_price": None,
        "stop_loss": None,
        "messages": [],
    }

    final_state = await graph.ainvoke(initial_state)

    signal_map = {s.value: s for s in SignalStrength}
    signal = signal_map.get(final_state["signal"], SignalStrength.HOLD)

    return EvaluationResult(
        ticker=ticker,
        signal=signal,
        confidence=final_state["confidence"],
        analyst_summary=final_state["final_decision"],
        risk_score=5.0,
        suggested_action=final_state["final_decision"],
        target_price=final_state.get("target_price"),
        stop_loss=final_state.get("stop_loss"),
        reasoning={
            "fundamentals": final_state["fundamentals_report"],
            "technical": final_state["technical_report"],
            "news": final_state["news_report"],
            "bull": final_state["bullish_case"],
            "bear": final_state["bearish_case"],
            "risk": final_state["risk_assessment"],
        },
    )
