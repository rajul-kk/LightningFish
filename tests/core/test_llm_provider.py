from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def _mock_anthropic_client(text: str = "0.4", input_tokens: int = 100, output_tokens: int = 5):
    client = MagicMock()
    response = MagicMock()
    response.content = [MagicMock(text=text)]
    response.usage.input_tokens = input_tokens
    response.usage.output_tokens = output_tokens
    client.messages.create.return_value = response
    return client


def _mock_openai_client(text: str = "0.3"):
    client = MagicMock()
    completion = MagicMock()
    completion.choices = [MagicMock(message=MagicMock(content=text))]
    client.chat.completions.create.return_value = completion
    return client


def test_anthropic_provider_returns_opinion_and_positive_cost():
    from lightningfish_core.llm_provider import AnthropicProvider
    client = _mock_anthropic_client("0.6")
    provider = AnthropicProvider(client)
    opinion, cost = provider.get_opinion("sys", "user", "claude-sonnet-4-6")
    assert opinion == pytest.approx(0.6)
    assert cost > 0.0


def test_anthropic_provider_clamps_out_of_range():
    from lightningfish_core.llm_provider import AnthropicProvider
    client = _mock_anthropic_client("5.0")
    provider = AnthropicProvider(client)
    opinion, _ = provider.get_opinion("sys", "user", "claude-sonnet-4-6")
    assert opinion == pytest.approx(1.0)


def test_anthropic_provider_handles_bad_text():
    from lightningfish_core.llm_provider import AnthropicProvider
    client = _mock_anthropic_client("not_a_number")
    provider = AnthropicProvider(client)
    opinion, _ = provider.get_opinion("sys", "user", "claude-sonnet-4-6")
    assert opinion == pytest.approx(0.0)


def test_local_provider_returns_zero_cost():
    from lightningfish_core.llm_provider import LocalProvider
    with patch("lightningfish_core.llm_provider.openai.OpenAI") as mock_cls:
        mock_cls.return_value = _mock_openai_client("0.3")
        provider = LocalProvider("http://localhost:11434/v1")
    opinion, cost = provider.get_opinion("sys", "user", "ollama:llama3.2")
    assert opinion == pytest.approx(0.3)
    assert cost == pytest.approx(0.0)


def test_local_provider_strips_ollama_prefix():
    from lightningfish_core.llm_provider import LocalProvider
    with patch("lightningfish_core.llm_provider.openai.OpenAI") as mock_cls:
        mock_instance = _mock_openai_client("0.1")
        mock_cls.return_value = mock_instance
        provider = LocalProvider("http://localhost:11434/v1")
    provider.get_opinion("sys", "user", "ollama:mistral")
    call_kwargs = mock_instance.chat.completions.create.call_args[1]
    assert call_kwargs["model"] == "mistral"


def test_make_provider_returns_anthropic_for_claude_model():
    from lightningfish_core.llm_provider import AnthropicProvider, make_provider
    with patch("lightningfish_core.llm_provider.Anthropic"):
        p = make_provider("claude-sonnet-4-6")
    assert isinstance(p, AnthropicProvider)


def test_make_provider_returns_local_for_ollama_prefix():
    from lightningfish_core.llm_provider import LocalProvider, make_provider
    with patch("lightningfish_core.llm_provider.openai.OpenAI"):
        p = make_provider("ollama:llama3.2")
    assert isinstance(p, LocalProvider)


def test_make_provider_returns_local_when_base_url_provided():
    from lightningfish_core.llm_provider import LocalProvider, make_provider
    with patch("lightningfish_core.llm_provider.openai.OpenAI"):
        p = make_provider("claude-sonnet-4-6", base_url="http://192.168.1.10:11434/v1")
    assert isinstance(p, LocalProvider)


# — new post generation + batch opinion tests —

def test_parse_post_response_valid():
    from lightningfish_core.llm_provider import _parse_post_response
    raw = "STANCE: bullish\nTAG: valuation\nCONFIDENCE: 0.72\nBLURB: Strong FCF yield signals upside.\n0.45"
    post, opinion = _parse_post_response(raw, agent_id="a1", archetype="Analyst", round_number=1, opinion_before=0.1)
    assert post.stance == "bullish"
    assert post.argument_tag == "valuation"
    assert abs(post.confidence - 0.72) < 0.001
    assert "FCF" in post.blurb
    assert abs(opinion - 0.45) < 0.001
    assert abs(post.opinion_after - 0.45) < 0.001


def test_parse_post_response_malformed_falls_back():
    from lightningfish_core.llm_provider import _parse_post_response
    raw = "I think this is bullish because earnings were great."
    post, opinion = _parse_post_response(raw, agent_id="a1", archetype="Analyst", round_number=1, opinion_before=0.2)
    assert post.argument_tag == "other"
    assert abs(opinion - 0.2) < 0.01


def test_parse_post_response_opinion_clamped():
    from lightningfish_core.llm_provider import _parse_post_response
    raw = "STANCE: bullish\nTAG: momentum\nCONFIDENCE: 0.9\nBLURB: Rocket.\n2.5"
    _, opinion = _parse_post_response(raw, agent_id="a1", archetype="T", round_number=1, opinion_before=0.0)
    assert opinion <= 1.0


def test_anthropic_generate_post_calls_messages_create():
    from lightningfish_core.llm_provider import AnthropicProvider
    raw = "STANCE: bearish\nTAG: macro\nCONFIDENCE: 0.8\nBLURB: Rate hikes incoming.\n-0.6"
    client = _mock_anthropic_client(raw, input_tokens=120, output_tokens=30)
    provider = AnthropicProvider(client)
    post, opinion, cost = provider.generate_post(
        system="You are a trader.", model="claude-sonnet-4-6",
        agent_id="a1", archetype="Trader", round_number=1, opinion_before=-0.2,
    )
    assert post.argument_tag == "macro"
    assert abs(opinion - (-0.6)) < 0.01
    assert cost > 0


def test_anthropic_batch_opinions_from_feed():
    from lightningfish_core.llm_provider import AnthropicProvider
    client = _mock_anthropic_client("-0.3\n0.5\n0.1", input_tokens=200, output_tokens=15)
    provider = AnthropicProvider(client)
    opinions, cost = provider.batch_opinions_from_feed(
        systems=["sys1", "sys2", "sys3"],
        model="claude-sonnet-4-6",
    )
    assert len(opinions) == 3
    assert abs(opinions[0] - (-0.3)) < 0.01
    assert cost > 0


def test_anthropic_batch_opinions_empty_input():
    from lightningfish_core.llm_provider import AnthropicProvider
    client = _mock_anthropic_client()
    provider = AnthropicProvider(client)
    opinions, cost = provider.batch_opinions_from_feed(systems=[], model="claude-sonnet-4-6")
    assert opinions == []
    assert cost == 0.0


def test_local_generate_post_parses_response():
    from lightningfish_core.llm_provider import LocalProvider
    raw = "STANCE: approve\nTAG: correctness\nCONFIDENCE: 0.85\nBLURB: Tests cover all paths.\n0.7"
    with patch("lightningfish_core.llm_provider.openai.OpenAI") as mock_cls:
        mock_cls.return_value = _mock_openai_client(raw)
        provider = LocalProvider()
    post, opinion, cost = provider.generate_post(
        system="You are a reviewer.", model="llama3",
        agent_id="b1", archetype="SeniorDev", round_number=2, opinion_before=0.3,
    )
    assert post.argument_tag == "correctness"
    assert abs(opinion - 0.7) < 0.01
    assert cost == 0.0
