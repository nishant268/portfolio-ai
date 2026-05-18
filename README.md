# Portfolio AI

AI-powered portfolio evaluator and sell-order engine, built by extending **TradingAgents** (tauricresearch/tradingagents).

## Architecture

```
Your Broker (Alpaca / Zerodha)
        │
        ▼
  Portfolio Loader   ←── fetches positions + prices
        │
        ▼
┌──────────────────────────────────────────────────┐
│         LangGraph Multi-Agent Pipeline            │
│                                                  │
│  FundamentalsAnalyst ──┐                         │
│  TechnicalAnalyst  ────┼──► BullishResearcher ◄─┐│
│  NewsAnalyst       ────┘    BearishResearcher ──┘│
│                                  │               │
│                             RiskManager          │
│                                  │               │
│                          PortfolioManager        │
│                        (SELL / HOLD decision)    │
└──────────────────────────────────────────────────┘
        │
        ▼
   SellOrder Engine
   (dry-run or live via broker API)
```

## Quick Start

```bash
cd portfolio-ai
cp .env.example .env        # fill in your keys
pip install -e ".[dev]"

# Evaluate a ticker manually (no broker account needed)
portfolio-ai evaluate --ticker AAPL --ticker TSLA --provider openai

# Evaluate your live Alpaca paper portfolio
portfolio-ai evaluate --broker alpaca

# Evaluate + auto-submit sell orders (dry-run by default — safe)
portfolio-ai sell --broker alpaca --dry-run true

# Go live (only when you're confident)
portfolio-ai sell --broker alpaca --dry-run false --min-confidence 0.75
```

## Supported LLM Providers

| Provider   | Env var            | Default model       |
|------------|--------------------|---------------------|
| openai     | OPENAI_API_KEY     | gpt-4o-mini         |
| anthropic  | ANTHROPIC_API_KEY  | claude-sonnet-4-6   |
| google     | GOOGLE_API_KEY     | gemini-1.5-flash    |
| ollama     | (none)             | llama3.1:8b (local) |

## Supported Brokers

| Broker  | Market | Notes |
|---------|--------|-------|
| alpaca  | US stocks, crypto | Paper & live; free API |
| zerodha | India NSE/BSE | Requires daily access token refresh |

## Signal Meanings

| Signal       | Meaning                          |
|-------------|----------------------------------|
| STRONG_SELL  | High conviction sell             |
| SELL         | Moderate sell recommendation     |
| HOLD         | Keep position                    |
| BUY          | Consider adding                  |
| STRONG_BUY   | High conviction add              |

## Extending the Agent Pipeline

The pipeline is standard LangGraph — add a node in `portfolio_ai/agents/portfolio_evaluator.py`:

```python
def my_custom_analyst(state: EvalState, llm) -> dict:
    ...
    return {"my_report": resp.content}

g.add_node("my_custom_analyst", lambda s: my_custom_analyst(s, llm))
g.add_edge("news_analyst", "my_custom_analyst")
g.add_edge("my_custom_analyst", "bullish_researcher")
```

## Adding a New Broker

Implement `BaseBroker` in `portfolio_ai/brokers/`:

```python
class MyBroker(BaseBroker):
    async def get_portfolio(self) -> Portfolio: ...
    async def get_current_price(self, ticker: str) -> float: ...
    async def submit_sell_order(self, order: SellOrder) -> SellOrder: ...
```

## Why TradingAgents over AI-Trader?

- **AI-Trader** is a social copy-trading platform — you follow others' signals via ai4trade.ai
- **TradingAgents** gives you a transparent, ownable LangGraph pipeline you can read, modify, and extend
- We add live broker integration + portfolio loading on top of TradingAgents' analysis engine
