"""
Programmatic backtest event source for the finance domain: (ticker, date) pairs
enriched into seeds, scored against the subsequent price move via
get_ground_truth.

CAVEAT: enrich_finance_seed pulls *current* headlines from yfinance, not the
headlines as they stood on ``filing_date``. The price ground truth is genuinely
point-in-time (yfinance serves historical prices by date), but the event text
is not, so this is closer to a forward test than a strict historical backtest.
Supplying explicit per-event context text (below) avoids the leak.
"""
from __future__ import annotations

from lightningfish_core.backtest import BacktestEvent

from .seed_enricher import enrich_finance_seed


def pull_ticker_events(
    events: list[tuple[str, str, str]],
) -> list[BacktestEvent]:
    """
    Build BacktestEvents from ``(ticker, filing_date, context_text)`` tuples.

    ``context_text`` is the point-in-time event description (a headline or
    filing snippet). Pass an empty string to fall back to live headlines —
    convenient but not point-in-time (see module caveat).
    """
    out: list[BacktestEvent] = []
    for ticker, filing_date, context_text in events:
        try:
            seed = enrich_finance_seed(ticker, context_text, filing_date)
        except Exception:
            continue
        out.append(BacktestEvent(event_id=f"{ticker}@{filing_date}", seed=seed))
    return out
