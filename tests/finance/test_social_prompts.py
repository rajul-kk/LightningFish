from __future__ import annotations

from lightningfish_core.models import AgentPersona, EnrichedSeed
from lightningfish_core.social import SocialPost
from lightningfish_finance.config import FinanceDomainAdapter


def _seed() -> EnrichedSeed:
    return EnrichedSeed(
        domain_id="finance",
        raw_input={},
        summary="AAPL reported strong earnings.",
        entities=["AAPL"],
        event_type="earnings",
        metadata={"ticker": "AAPL"},
    )


def _persona() -> AgentPersona:
    return AgentPersona(
        unique_id="a1",
        archetype="InstitutionalAnalyst",
        opinion_resistance=0.6,
        recency_bias=0.4,
        contrarian_tendency=0.3,
        influence_weight=0.9,
        proportion=0.1,
        herding_coefficient=0.2,
    )


def test_finance_taxonomy_length():
    adapter = FinanceDomainAdapter()
    taxonomy = adapter.argument_taxonomy()
    assert len(taxonomy) == 8
    assert "valuation" in taxonomy
    assert "momentum" in taxonomy


def test_finance_post_prompt_includes_taxonomy():
    adapter = FinanceDomainAdapter()
    prompt = adapter.post_system_prompt(_seed(), _persona(), feed=[], viral=None)
    for tag in adapter.argument_taxonomy():
        assert tag in prompt


def test_finance_post_prompt_includes_format_instructions():
    adapter = FinanceDomainAdapter()
    prompt = adapter.post_system_prompt(_seed(), _persona(), feed=[], viral=None)
    assert "STANCE:" in prompt
    assert "TAG:" in prompt
    assert "CONFIDENCE:" in prompt
    assert "BLURB:" in prompt


def test_finance_post_prompt_includes_feed_posts():
    adapter = FinanceDomainAdapter()
    feed = [SocialPost(
        agent_id="x", archetype="ValueInvestor", round_number=1,
        stance="bearish", argument_tag="valuation", confidence=0.8,
        blurb="P/E is stretched.", opinion_before=0.0, opinion_after=-0.2,
    )]
    prompt = adapter.post_system_prompt(_seed(), _persona(), feed=feed, viral=None)
    assert "P/E is stretched" in prompt


def test_finance_post_prompt_includes_viral_post():
    adapter = FinanceDomainAdapter()
    viral = SocialPost(
        agent_id="v", archetype="ShortSeller", round_number=1,
        stance="bearish", argument_tag="liquidity", confidence=0.95,
        blurb="Balance sheet looks stressed.", opinion_before=-0.1, opinion_after=-0.5,
    )
    prompt = adapter.post_system_prompt(_seed(), _persona(), feed=[], viral=viral)
    assert "Balance sheet looks stressed" in prompt
