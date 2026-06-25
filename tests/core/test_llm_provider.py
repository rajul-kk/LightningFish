from __future__ import annotations
import pytest
from unittest.mock import MagicMock, patch


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
