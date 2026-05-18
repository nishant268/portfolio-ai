"""
CLI entrypoint.

Usage examples:
  portfolio-ai evaluate --broker alpaca
  portfolio-ai evaluate --broker zerodha --provider anthropic
  portfolio-ai sell --broker alpaca --dry-run false
  portfolio-ai evaluate --ticker AAPL --ticker TSLA  # manual tickers (no broker)
"""
from __future__ import annotations

import asyncio
import os
from typing import Optional

import typer
from rich import print as rprint
from rich.console import Console
from rich.table import Table

from portfolio_ai.models.portfolio import Portfolio, Position, AssetClass

app = typer.Typer(help="AI Portfolio Evaluator — powered by TradingAgents multi-agent pipeline")
console = Console()


def _load_broker(broker: str, paper: bool = True):
    if broker == "alpaca":
        from portfolio_ai.brokers.alpaca import AlpacaBroker
        return AlpacaBroker(paper=paper)
    elif broker == "zerodha":
        from portfolio_ai.brokers.zerodha import ZerodhaBroker
        return ZerodhaBroker()
    else:
        raise typer.BadParameter(f"Unknown broker: {broker}. Choose: alpaca, zerodha")


def _display_portfolio(portfolio: Portfolio) -> None:
    table = Table(title="Portfolio", show_lines=True)
    table.add_column("Ticker", style="cyan")
    table.add_column("Qty", justify="right")
    table.add_column("Avg Cost", justify="right")
    table.add_column("Current", justify="right")
    table.add_column("Market Value", justify="right")
    table.add_column("P&L", justify="right")
    table.add_column("P&L %", justify="right")

    for p in portfolio.positions:
        pnl_color = "green" if p.unrealized_pnl >= 0 else "red"
        table.add_row(
            p.ticker,
            f"{p.quantity:.4f}",
            f"${p.avg_cost:.2f}",
            f"${p.current_price:.2f}",
            f"${p.market_value:,.2f}",
            f"[{pnl_color}]${p.unrealized_pnl:,.2f}[/]",
            f"[{pnl_color}]{p.unrealized_pnl_pct:.1f}%[/]",
        )

    console.print(table)
    console.print(
        f"  Total value: [bold]${portfolio.total_value:,.2f}[/]  "
        f"Cash: [bold]${portfolio.cash:,.2f}[/]  "
        f"Total P&L: [bold {'green' if portfolio.total_unrealized_pnl >= 0 else 'red'}]"
        f"${portfolio.total_unrealized_pnl:,.2f} ({portfolio.total_pnl_pct:.1f}%)[/]"
    )


def _display_evaluations(results) -> None:
    table = Table(title="Evaluation Results", show_lines=True)
    table.add_column("Ticker", style="cyan")
    table.add_column("Signal", justify="center")
    table.add_column("Confidence", justify="right")
    table.add_column("Target", justify="right")
    table.add_column("Stop Loss", justify="right")
    table.add_column("Action")

    signal_colors = {
        "STRONG_SELL": "bold red",
        "SELL": "red",
        "HOLD": "yellow",
        "BUY": "green",
        "STRONG_BUY": "bold green",
    }

    for r in results:
        color = signal_colors.get(r.signal.value, "white")
        table.add_row(
            r.ticker,
            f"[{color}]{r.signal.value}[/]",
            f"{r.confidence:.0%}",
            f"${r.target_price:.2f}" if r.target_price else "-",
            f"${r.stop_loss:.2f}" if r.stop_loss else "-",
            r.suggested_action[:60] + "..." if len(r.suggested_action) > 60 else r.suggested_action,
        )

    console.print(table)


@app.command()
def evaluate(
    broker: Optional[str] = typer.Option(None, help="alpaca | zerodha"),
    ticker: Optional[list[str]] = typer.Option(None, help="Manual ticker(s) if no broker"),
    provider: str = typer.Option("openai", help="LLM provider: openai | anthropic | google | ollama"),
    model: Optional[str] = typer.Option(None, help="Model name override"),
    paper: bool = typer.Option(True, help="Use paper/sandbox broker account"),
    avg_cost: Optional[float] = typer.Option(None, help="Average cost for manual tickers"),
    qty: float = typer.Option(1.0, help="Quantity for manual tickers"),
):
    """Fetch your portfolio and run AI evaluation on every position."""

    async def _run():
        from portfolio_ai.agents.portfolio_evaluator import evaluate_position

        if broker:
            b = _load_broker(broker, paper=paper)
            portfolio = await b.get_portfolio()
        elif ticker:
            import yfinance as yf
            positions = []
            for t in ticker:
                price = float(yf.Ticker(t).fast_info.last_price or 0)
                positions.append(Position(
                    ticker=t,
                    asset_class=AssetClass.STOCK,
                    quantity=qty,
                    avg_cost=avg_cost or price,
                    current_price=price,
                ))
            portfolio = Portfolio(positions=positions, cash=0.0)
        else:
            console.print("[red]Provide --broker or --ticker[/red]")
            raise typer.Exit(1)

        _display_portfolio(portfolio)

        console.print(f"\n[bold]Running AI evaluation on {len(portfolio.positions)} position(s)...[/bold]\n")

        results = []
        for pos in portfolio.positions:
            console.print(f"  Analyzing [cyan]{pos.ticker}[/cyan]...", end=" ")
            result = await evaluate_position(pos, provider=provider, model=model)
            results.append(result)
            console.print(f"[bold]{result.signal.value}[/bold]")

        _display_evaluations(results)
        return results

    asyncio.run(_run())


@app.command()
def sell(
    broker: str = typer.Option(..., help="alpaca | zerodha"),
    provider: str = typer.Option("openai", help="LLM provider"),
    model: Optional[str] = typer.Option(None),
    dry_run: bool = typer.Option(True, help="Simulate orders without submitting"),
    use_limit: bool = typer.Option(False, help="Use limit orders instead of market"),
    paper: bool = typer.Option(True, help="Paper broker account"),
    min_confidence: float = typer.Option(0.6, help="Minimum confidence to trigger a sell"),
):
    """Evaluate portfolio and auto-submit SELL orders for recommended positions."""

    async def _run():
        from portfolio_ai.agents.portfolio_evaluator import evaluate_position
        from portfolio_ai.tools.sell_engine import build_sell_order, execute_sell_orders
        from portfolio_ai.models.portfolio import SignalStrength

        b = _load_broker(broker, paper=paper)
        portfolio = await b.get_portfolio()
        _display_portfolio(portfolio)

        console.print(f"\n[bold]Evaluating {len(portfolio.positions)} position(s)...[/bold]\n")

        orders = []
        for pos in portfolio.positions:
            console.print(f"  Analyzing [cyan]{pos.ticker}[/cyan]...", end=" ")
            result = await evaluate_position(pos, provider=provider, model=model)
            console.print(f"[bold]{result.signal.value}[/bold] ({result.confidence:.0%})")

            if result.confidence < min_confidence:
                console.print(f"    [dim]Skipped — confidence {result.confidence:.0%} < {min_confidence:.0%}[/dim]")
                continue

            order = build_sell_order(pos, result, dry_run=dry_run, use_limit=use_limit)
            if order:
                orders.append(order)
                console.print(f"    [red]SELL ORDER queued: {order.quantity} {order.ticker} ({order.order_type.value})[/red]")
            else:
                console.print(f"    [green]Hold — no sell order[/green]")

        if not orders:
            console.print("\n[green]No sell orders generated.[/green]")
            return

        console.print(f"\n[bold]{'[DRY RUN] ' if dry_run else ''}Submitting {len(orders)} sell order(s)...[/bold]")
        submitted = await execute_sell_orders(orders, b)

        table = Table(title="Order Results")
        table.add_column("Ticker")
        table.add_column("Qty", justify="right")
        table.add_column("Type")
        table.add_column("Status")
        table.add_column("Broker ID")
        table.add_column("Reason")

        for o in submitted:
            table.add_row(
                o.ticker,
                str(o.quantity),
                o.order_type.value,
                o.status,
                o.broker_order_id or "-",
                o.reason[:50],
            )
        console.print(table)

    asyncio.run(_run())


if __name__ == "__main__":
    app()
