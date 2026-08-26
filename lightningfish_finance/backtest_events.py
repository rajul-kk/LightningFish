"""
Programmatic backtest event sources for the finance domain.

POINT-IN-TIME: the price ground truth is genuinely historical (yfinance serves
prices by date), but enrich_finance_seed would otherwise pull *current* headlines,
a hindsight leak. So both pullers below require genuine point-in-time context
text; events without it are skipped rather than silently backfilled with today's
news. (For live/forward use, call enrich_finance_seed directly instead.)
"""
from __future__ import annotations

import html
import os
import re
from datetime import date, timedelta
from pathlib import Path

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
            continue  # no point-in-time text, would leak current news; skip
        try:
            seed = enrich_finance_seed(ticker, context_text, filing_date)
        except Exception:
            continue
        out.append(BacktestEvent(event_id=f"{ticker}@{filing_date}", seed=seed))
    return out


# Diverse tickers across sectors and market caps, so pulling the first few
# filings from each doesn't just sample one industry's reporting calendar.
_DEFAULT_TICKERS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "NVDA", "JPM",
    "BAC", "WMT", "PFE", "JNJ", "XOM", "CVX", "GE", "BA", "DIS",
    "NFLX", "UBER", "LYFT", "SNAP", "RIVN", "PLTR", "COIN",
    "AMC", "GME", "SPCE", "LCID", "F", "GM",
]

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_FILED_DATE_RE = re.compile(r"FILED AS OF DATE:\s*(\d{8})")
_MAX_FILING_CHARS = 4000
_ITEM_HEADER_RE = re.compile(r"Item\s+\d\.\d\d")


def _clean_filing_text(raw_html: str) -> str:
    """
    SEC filings are inline-XBRL-tagged HTML; agents read plain text.

    Every 8-K opens with a cover page, checkbox disclosures, registrant
    name, trading symbol table, none of which mentions what happened. On a
    real filing this ran ~2800 characters before the first "Item 5.02" (or
    similar) section header, where the substantive disclosure starts.
    Truncating from character 0 mostly captured boilerplate and cut off the
    real content, also why every seed built this way classified as the same
    generic event type: the keyword classifier had only boilerplate to look at.
    """
    text = _TAG_RE.sub(" ", raw_html)
    text = html.unescape(text)
    text = _WS_RE.sub(" ", text).strip()
    m = _ITEM_HEADER_RE.search(text)
    if m:
        text = text[m.start():]
    return text[:_MAX_FILING_CHARS]


def _filed_date(full_submission_text: str) -> str | None:
    """Parses the SEC header's FILED AS OF DATE (YYYYMMDD) into YYYY-MM-DD.
    This is the as-filed date, independent of when this script runs."""
    m = _FILED_DATE_RE.search(full_submission_text)
    if not m:
        return None
    raw = m.group(1)
    return f"{raw[:4]}-{raw[4:6]}-{raw[6:]}"


def pull_edgar_events(
    n: int = 30,
    tickers: list[str] | None = None,
    settlement_buffer_days: int = 3,
    download_dir: str = ".cache/lightningfish/sec_edgar",
) -> list[BacktestEvent]:
    """
    Download real 8-K filings from SEC EDGAR and build point-in-time
    BacktestEvents from their as-filed text, the same words a reader would
    have seen on the filing date, never anything written after.

    Requires SEC_EDGAR_USER_AGENT as "Your Name you@example.com" (SEC's fair
    access policy requires a real identifying user agent, not an app name).

    settlement_buffer_days: filings newer than this are excluded. The ground
    truth (get_finance_ground_truth) measures the 72h price move after filing;
    without this floor, a very recent filing would score against a move that
    hasn't finished happening yet, not a skip, a silently wrong measurement.
    """
    from sec_edgar_downloader import Downloader

    ua = os.environ.get("SEC_EDGAR_USER_AGENT", "")
    parts = ua.rsplit(" ", 1)
    if len(parts) != 2:
        raise ValueError(
            "SEC_EDGAR_USER_AGENT must be set as 'Your Name you@example.com' "
            "(SEC requires a real identifying user agent, not just an app name)"
        )
    company_name, email = parts

    dl = Downloader(company_name, email, download_folder=download_dir)
    cutoff = date.today() - timedelta(days=settlement_buffer_days)

    events: list[BacktestEvent] = []
    for ticker in (tickers or _DEFAULT_TICKERS):
        if len(events) >= n:
            break
        try:
            dl.get("8-K", ticker, limit=2, download_details=True, before=cutoff.isoformat())
        except Exception:
            continue

        ticker_dir = Path(download_dir) / "sec-edgar-filings" / ticker / "8-K"
        if not ticker_dir.exists():
            continue
        for accession_dir in sorted(ticker_dir.iterdir()):
            if len(events) >= n:
                break
            submission_path = accession_dir / "full-submission.txt"
            doc_path = accession_dir / "primary-document.html"
            if not submission_path.exists() or not doc_path.exists():
                continue

            filing_date = _filed_date(submission_path.read_text(encoding="utf-8", errors="replace"))
            if not filing_date:
                continue
            filing_text = _clean_filing_text(doc_path.read_text(encoding="utf-8", errors="replace"))
            if not filing_text:
                continue

            try:
                seed = enrich_finance_seed(ticker, filing_text, filing_date)
            except Exception:
                continue
            events.append(BacktestEvent(event_id=f"{ticker}@{filing_date}", seed=seed))

    return events
