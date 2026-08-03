from __future__ import annotations

from lightningfish_finance.backtest_events import pull_ticker_events


def test_events_without_point_in_time_text_are_skipped():
    # Empty/whitespace context must be dropped before any enrichment (which would
    # otherwise leak current headlines into a historical backtest). No network.
    assert pull_ticker_events([("AAPL", "2024-01-01", "")]) == []
    assert pull_ticker_events([("AAPL", "2024-01-01", "   ")]) == []
