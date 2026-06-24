from __future__ import annotations
import yfinance as yf
from lightningfish_core.models import EnrichedSeed

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


def enrich_finance_seed(ticker: str, filing_text: str, filing_date: str) -> EnrichedSeed:
    event_type = classify_event_type(filing_text)

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
        f"{ticker} filed an 8-K reporting a {event_type.replace('_', ' ')} event. "
        f"Sector: {sector}, market cap: {cap_tier}-cap."
    )

    return EnrichedSeed(
        domain_id="finance",
        raw_input={"ticker": ticker, "filing_text": filing_text, "filing_date": filing_date},
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
