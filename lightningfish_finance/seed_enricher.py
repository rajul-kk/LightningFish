from __future__ import annotations

import re

import yfinance as yf

from lightningfish_core.models import EnrichedSeed

_TICKER_RE = re.compile(r"^[A-Z]{1,5}(\.[A-Z]{1,2})?$")  # e.g. AAPL, BRK.B

_EVENT_KEYWORDS: dict[str, list[str]] = {
    "earnings_beat":  ["beat", "exceeded", "surpassed", "outperformed", "above estimates", "better than expected"],
    "earnings_miss":  ["missed", "below estimates", "fell short", "disappointing", "below expectations"],
    "ceo_change":     ["ceo", "chief executive", "president", "leadership change", "appointed", "resigned", "stepping down"],
    "regulatory":     ["fda", "sec", "ftc", "doj", "regulatory", "investigation", "fine", "penalty", "settlement"],
    "m_and_a":        ["merger", "acquisition", "acquire", "takeover", "deal", "purchase", "combine"],
    "macro":          ["interest rate", "inflation", "gdp", "recession", "federal reserve", "fed funds"],
}


def classify_event_type(text: str) -> str:
    lower = text.lower()
    scores = {
        event: sum(1 for kw in keywords if kw in lower)
        for event, keywords in _EVENT_KEYWORDS.items()
    }
    best, score = max(scores.items(), key=lambda kv: kv[1])
    return best if score > 0 else "other"


def _fetch_recent_headlines(ticker: str) -> str:
    """Pull up to 3 recent news headlines from yfinance as context."""
    try:
        news = yf.Ticker(ticker).news or []
        titles = []
        for item in news[:5]:
            title = (
                item.get("content", {}).get("title")  # yfinance >= 0.2.54
                or item.get("title")                   # older versions
                or ""
            )
            if title:
                titles.append(title)
        if titles:
            return "Recent headlines: " + ". ".join(titles[:3]) + "."
    except Exception:
        pass
    return f"Recent market activity for {ticker}."


def enrich_finance_seed(ticker: str, filing_text: str, filing_date: str) -> EnrichedSeed:
    ticker = ticker.strip().upper()
    if not _TICKER_RE.match(ticker):
        raise ValueError(f"Invalid ticker format: {ticker!r}")

    # If no context was provided, use live headlines so users don't need to paste anything.
    context = filing_text.strip() if filing_text.strip() else _fetch_recent_headlines(ticker)
    event_type = classify_event_type(context)

    info = yf.Ticker(ticker).info
    sector = info.get("sector", "unknown")
    market_cap = info.get("marketCap") or 0
    if market_cap > 200e9:
        cap_tier = "large"
    elif market_cap > 10e9:
        cap_tier = "mid"
    else:
        cap_tier = "small"

    summary = (
        f"{ticker}: {event_type.replace('_', ' ')} event. "
        f"Sector: {sector}, {cap_tier}-cap. Context: {context[:200]}"
    )

    return EnrichedSeed(
        domain_id="finance",
        raw_input={"ticker": ticker, "filing_text": context, "filing_date": filing_date},
        summary=summary,
        entities=[ticker, sector],
        event_type=event_type,
        metadata={
            "ticker": ticker,
            "sector": sector,
            "market_cap_tier": cap_tier,
            "filing_date": filing_date,
        },
    )
