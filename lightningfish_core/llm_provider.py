from __future__ import annotations
from typing import Protocol, runtime_checkable
from anthropic import Anthropic
import openai

_MODEL_COSTS: dict[str, tuple[float, float]] = {
    "claude-haiku-4-5-20251001": (0.8e-6,  4e-6),
    "claude-sonnet-4-6":         (3e-6,   15e-6),
    "claude-opus-4-8":           (15e-6,  75e-6),
}
_DEFAULT_COSTS = (3e-6, 15e-6)
_LOCAL_BASE_URL = "http://localhost:11434/v1"


@runtime_checkable
class LLMProvider(Protocol):
    def get_opinion(self, system: str, user_msg: str, model: str) -> tuple[float, float]:
        """Return (opinion in [-1, 1], cost_usd >= 0)."""
        ...


class AnthropicProvider:
    def __init__(self, client: Anthropic) -> None:
        self._client = client

    def get_opinion(self, system: str, user_msg: str, model: str) -> tuple[float, float]:
        response = self._client.messages.create(
            model=model,
            max_tokens=16,
            system=system,
            messages=[{"role": "user", "content": user_msg}],
        )
        text = response.content[0].text.strip()
        try:
            opinion = max(-1.0, min(1.0, float(text)))
        except ValueError:
            opinion = 0.0
        in_cost, out_cost = _MODEL_COSTS.get(model, _DEFAULT_COSTS)
        cost = response.usage.input_tokens * in_cost + response.usage.output_tokens * out_cost
        return opinion, cost


class LocalProvider:
    """OpenAI-compatible local inference — Ollama, llama.cpp, vLLM, etc."""

    def __init__(self, base_url: str = _LOCAL_BASE_URL) -> None:
        self._client = openai.OpenAI(base_url=base_url, api_key="local")

    def get_opinion(self, system: str, user_msg: str, model: str) -> tuple[float, float]:
        # Ollama expects bare model names, not the "ollama:" prefix
        bare_model = model.split(":", 1)[-1] if ":" in model else model
        response = self._client.chat.completions.create(
            model=bare_model,
            max_tokens=16,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_msg},
            ],
        )
        text = (response.choices[0].message.content or "").strip()
        try:
            opinion = max(-1.0, min(1.0, float(text)))
        except ValueError:
            opinion = 0.0
        return opinion, 0.0  # local inference: zero API cost


def make_provider(model: str, base_url: str | None = None) -> LLMProvider:
    """Return AnthropicProvider for Claude models, LocalProvider otherwise."""
    if model.startswith("ollama:") or base_url is not None:
        return LocalProvider(base_url=base_url or _LOCAL_BASE_URL)
    return AnthropicProvider(Anthropic())
