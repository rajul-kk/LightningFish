from __future__ import annotations

import datetime
import os

import praw
import yfinance as yf

from lightningfish_core.models import GroundTruthRecord

_SUBREDDITS = ["wallstreetbets", "investing", "stocks"]
_SENTIMENT_POSITIVE = ["bull", "long", "buy", "moon", "beat", "surge", "pump", "bullish"]
_SENTIMENT_NEGATIVE = ["bear", "short", "sell", "crash", "miss", "dump", "tank", "bearish"]


def _score_post(text: str) -> float:
    lower = text.lower()
    pos = sum(1 for w in _SENTIMENT_POSITIVE if w in lower)
    neg = sum(1 for w in _SENTIMENT_NEGATIVE if w in lower)
    total = pos + neg
    if total == 0:
        return 0.0
    return (pos - neg) / total


def get_finance_ground_truth(ticker: str, filing_date: str) -> GroundTruthRecord:
    start = datetime.datetime.fromisoformat(filing_date)
    end = start + datetime.timedelta(hours=72)

    reddit = praw.Reddit(
        client_id=os.environ["REDDIT_CLIENT_ID"],
        client_secret=os.environ["REDDIT_CLIENT_SECRET"],
        user_agent=os.environ.get("REDDIT_USER_AGENT", "lightningfish/0.1"),
    )

    sentiment_scores: list[float] = []
    for sub_name in _SUBREDDITS:
        sub = reddit.subreddit(sub_name)
        for post in sub.search(ticker, sort="new", time_filter="week", limit=50):
            text = f"{post.title} {post.selftext}"
            sentiment_scores.append(_score_post(text))

    sentiment_series = sentiment_scores if sentiment_scores else [0.0]

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
        "sentiment_series": sentiment_series,
        "price_series": price_series,
        "price_change_pct": price_change_pct,
    })
