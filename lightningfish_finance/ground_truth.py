from __future__ import annotations

import datetime

import yfinance as yf

from lightningfish_core.models import GroundTruthRecord


def get_finance_ground_truth(ticker: str, filing_date: str) -> GroundTruthRecord:
    """
    The price move in the 72h after ``filing_date``. Point-in-time safe:
    yfinance serves actual historical OHLC bars by date, so this never reads
    anything that wasn't already public by the time the window closes.

    Earlier versions also fetched Reddit sentiment as a second signal (via
    subreddit search with time_filter="week"). That window was relative to
    when the fetch ran, not to filing_date, so anything over a week old got
    unrelated chatter or nothing: a real point-in-time violation, and one
    scoring never needed anyway, since truth_direction only reads
    price_change_pct. Dropped rather than fixed: a genuinely historical
    Reddit search isn't available through this API at all.
    """
    start = datetime.datetime.fromisoformat(filing_date)
    end = start + datetime.timedelta(hours=72)

    price_df = yf.download(
        ticker,
        start=start.date(),
        end=(end + datetime.timedelta(days=1)).date(),
        interval="1h",
        progress=False,
    )
    price_series: list[float] = price_df["Close"].dropna().tolist()
    price_change_pct = (
        (price_series[-1] - price_series[0]) / price_series[0]
        if len(price_series) >= 2
        else 0.0
    )

    return GroundTruthRecord(data={
        "price_series": price_series,
        "price_change_pct": price_change_pct,
    })
