"""
Programmatic backtest event source for the finance domain: (ticker, date,
headline) triples enriched into seeds, scored against the subsequent price move
via get_ground_truth.

POINT-IN-TIME: the price ground truth is genuinely historical (yfinance serves
prices by date), but enrich_finance_seed would otherwise pull *current* headlines
— a hindsight leak. So backtest events REQUIRE explicit point-in-time context
text; events without it are skipped rather than silently backfilled with today's
news. (For live/forward use, call enrich_finance_seed directly instead.)
"""
from __future__ import annotations

from lightningfish_core.backtest import BacktestEvent

from .seed_enricher import enrich_finance_seed


def pull_ticker_events(
    events: list[tuple[str, str, str]],
) -> list[BacktestEvent]:
    """
    Build BacktestEvents from ``(ticker, filing_date, context_text)`` triples.

    ``context_text`` must be the point-in-time event description (a headline or
    filing snippet as it stood on ``filing_date``). Triples with empty context
    are skipped to prevent leaking current headlines into a historical backtest.
    """
    out: list[BacktestEvent] = []
    for ticker, filing_date, context_text in events:
        if not context_text.strip():
            continue  # no point-in-time text → would leak current news; skip
        try:
            seed = enrich_finance_seed(ticker, context_text, filing_date)
        except Exception:
            continue
        out.append(BacktestEvent(event_id=f"{ticker}@{filing_date}", seed=seed))
    return out
