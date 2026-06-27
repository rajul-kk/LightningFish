from unittest.mock import patch

from lightningfish_core.models import EnrichedSeed
from lightningfish_finance.seed_enricher import classify_event_type, enrich_finance_seed


def test_classify_earnings_beat():
    assert classify_event_type("Company exceeded analyst estimates by 15%") == "earnings_beat"


def test_classify_ceo_change():
    assert classify_event_type("Board appoints new Chief Executive Officer effective immediately") == "ceo_change"


def test_classify_regulatory():
    assert classify_event_type("SEC investigation into trading practices") == "regulatory"


def test_classify_m_and_a():
    assert classify_event_type("Company announces acquisition of rival firm") == "m_and_a"


def test_classify_fallback_to_other():
    assert classify_event_type("Routine quarterly dividend declared") == "other"


def test_enrich_returns_enriched_seed():
    mock_info = {"sector": "Technology", "marketCap": 500_000_000_000}
    with patch("lightningfish_finance.seed_enricher.yf.Ticker") as mock_ticker:
        mock_ticker.return_value.info = mock_info
        result = enrich_finance_seed("AAPL", "CEO resigned today", "2024-01-15")

    assert isinstance(result, EnrichedSeed)
    assert result.domain_id == "finance"
    assert result.metadata["ticker"] == "AAPL"
    assert result.metadata["market_cap_tier"] == "large"
    assert result.metadata["filing_date"] == "2024-01-15"
    assert result.event_type == "ceo_change"
