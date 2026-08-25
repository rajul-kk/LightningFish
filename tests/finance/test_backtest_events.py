from __future__ import annotations

import pytest

from lightningfish_finance.backtest_events import (
    _clean_filing_text,
    _filed_date,
    pull_edgar_events,
    pull_ticker_events,
)


def test_events_without_point_in_time_text_are_skipped():
    # Empty/whitespace context must be dropped before any enrichment (which would
    # otherwise leak current headlines into a historical backtest). No network.
    assert pull_ticker_events([("AAPL", "2024-01-01", "")]) == []
    assert pull_ticker_events([("AAPL", "2024-01-01", "   ")]) == []


def test_filed_date_parses_sec_header_format():
    header = "CONFORMED PERIOD OF REPORT:\t20260430\nFILED AS OF DATE:\t\t20260430\n"
    assert _filed_date(header) == "2026-04-30"


def test_filed_date_returns_none_when_absent():
    assert _filed_date("no header here") is None


def test_clean_filing_text_strips_tags_and_entities():
    raw = "<html><body><p>Revenue up 12% &amp; guidance raised</p></body></html>"
    cleaned = _clean_filing_text(raw)
    assert "<" not in cleaned
    assert "&amp;" not in cleaned
    assert "Revenue up 12% & guidance raised" in cleaned


def test_clean_filing_text_collapses_whitespace_and_truncates():
    raw = "<p>word</p>\n\n\n" * 2000
    cleaned = _clean_filing_text(raw)
    assert "  " not in cleaned
    assert len(cleaned) <= 4000


def test_clean_filing_text_skips_cover_page_boilerplate():
    # Real 8-Ks open with checkbox disclosures and a symbol table before the
    # actual "Item X.XX" section that says what happened. Truncating from
    # character 0 mostly captured that boilerplate; this checks it's skipped.
    boilerplate = "<p>Registrant name, address, checkboxes</p>" * 50
    substance = "<p>Item 5.02 Departure of Directors; the CEO has resigned effective immediately.</p>"
    cleaned = _clean_filing_text(boilerplate + substance)
    assert cleaned.startswith("Item 5.02")
    assert "CEO has resigned" in cleaned


def test_clean_filing_text_falls_back_when_no_item_header_found():
    cleaned = _clean_filing_text("<p>Some filing text with no item header</p>")
    assert "Some filing text" in cleaned


def test_pull_edgar_events_requires_a_well_formed_user_agent(monkeypatch):
    monkeypatch.delenv("SEC_EDGAR_USER_AGENT", raising=False)
    with pytest.raises(ValueError, match="SEC_EDGAR_USER_AGENT"):
        pull_edgar_events()

    monkeypatch.setenv("SEC_EDGAR_USER_AGENT", "JustAName")  # no email half
    with pytest.raises(ValueError, match="SEC_EDGAR_USER_AGENT"):
        pull_edgar_events()
