from lightningfish_core.models import (
    EnrichedSeed,
    GroundTruthRecord,
    SimulationResult,
)
from lightningfish_finance.config import FinanceDomainAdapter


def _seed() -> EnrichedSeed:
    return EnrichedSeed(
        "finance",
        {"ticker": "AAPL", "filing_text": "CEO resigned", "filing_date": "2024-01-15"},
        "AAPL filed a ceo_change 8-K.", ["AAPL", "Technology"], "ceo_change",
        {"ticker": "AAPL", "sector": "Technology", "market_cap_tier": "large", "filing_date": "2024-01-15"},
    )


def _result(trajectory: list) -> SimulationResult:
    return SimulationResult(
        seed=_seed(), trajectory=trajectory,
        round_events=[], final_distribution=trajectory,
        total_tier1_calls=5, total_cost_usd=0.02,
    )


def test_adapter_contract_satisfied():
    adapter = FinanceDomainAdapter()
    assert adapter.domain_id == "finance"
    assert len(adapter.opinion_labels) == 2


def test_build_personas_returns_list():
    adapter = FinanceDomainAdapter()
    personas = adapter.build_personas(100)
    assert len(personas) > 0
    assert all(hasattr(p, "archetype") for p in personas)


def test_agent_system_prompt_contains_archetype():
    adapter = FinanceDomainAdapter()
    persona = adapter.build_personas(10)[0]
    prompt = adapter.agent_system_prompt(_seed(), persona)
    assert persona.archetype in prompt


def test_naive_prediction_reads_full_filing_text_not_truncated_summary():
    # seed.summary truncates context to 200 chars for display; naive_prediction
    # must read raw_input["filing_text"] instead, or it never sees keywords
    # that fall past that truncation point. Reproduces the real bug: a real
    # run scored 6% (near-degenerate) because it was reading the truncated
    # summary, which after the Item-header-skip fix is mostly boilerplate.
    adapter = FinanceDomainAdapter()
    seed = EnrichedSeed(
        "finance",
        {"ticker": "AAPL", "filing_text": "x" * 250 + " beat estimates", "filing_date": "2024-01-15"},
        "AAPL: earnings event. Sector: Technology, large-cap. Context: " + "x" * 200,
        ["AAPL"], "earnings_beat",
        {"ticker": "AAPL"},
    )
    assert adapter.naive_prediction(seed) > 0


def test_naive_prediction_falls_back_to_summary_when_filing_text_missing():
    adapter = FinanceDomainAdapter()
    seed = EnrichedSeed(
        "finance", {"ticker": "AAPL", "filing_date": "2024-01-15"},
        "AAPL missed estimates badly", ["AAPL"], "earnings_miss", {"ticker": "AAPL"},
    )
    assert adapter.naive_prediction(seed) < 0


def test_score_direction_match():
    adapter = FinanceDomainAdapter()
    truth = GroundTruthRecord(data={
        "price_series": [100.0, 102.0, 105.0],
        "price_change_pct": 0.05,
    })
    scored = adapter.score(_result([0.1, 0.2, 0.4]), truth)
    assert scored.direction_match is True
    assert scored.magnitude_correlation == 0.0


def test_score_direction_mismatch_price():
    adapter = FinanceDomainAdapter()
    truth = GroundTruthRecord(data={
        "price_series": [100.0, 99.0, 98.0],
        "price_change_pct": -0.02,
    })
    scored = adapter.score(_result([0.1, 0.2, 0.4]), truth)
    assert scored.domain_metric["price_direction_match"] is False
    assert "price_change_pct" in scored.domain_metric
