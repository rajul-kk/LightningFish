from __future__ import annotations

import os
from typing import TYPE_CHECKING, Protocol, runtime_checkable

import openai
from anthropic import Anthropic

if TYPE_CHECKING:
    from .social import SocialPost

_MODEL_COSTS: dict[str, tuple[float, float]] = {
    "claude-haiku-4-5-20251001": (1e-6,   5e-6),
    "claude-sonnet-5":           (3e-6,  15e-6),
    "claude-opus-5":             (5e-6,  25e-6),
}
_DEFAULT_COSTS = (3e-6, 15e-6)
_LOCAL_BASE_URL = "http://localhost:11434/v1"

# Local inference on a CPU-only or otherwise loaded host is slow, but it must
# be BOUNDED. The OpenAI SDK defaults to a 600s timeout with 2 retries, so a
# single wedged request can stall a multi-hour backtest for 30 minutes with no
# output — observed hanging an HN run indefinitely at event 12 of 36.
_LOCAL_TIMEOUT_SECONDS = float(os.environ.get("LIGHTNINGFISH_LOCAL_TIMEOUT", "240"))

_POST_USER_MSG = "Write your post and updated opinion now."
_BATCH_USER_SUFFIX = "Return exactly {n} opinion floats, one per line, in agent order. Range -1.0 to 1.0. No other text."


def _parse_post_response(
    raw: str,
    agent_id: str,
    archetype: str,
    round_number: int,
    opinion_before: float,
) -> "tuple[SocialPost, float]":
    """
    Parse the constrained post format:
        STANCE: bullish|bearish|approve|block
        TAG: <tag>
        CONFIDENCE: <float>
        BLURB: <sentence>
        <float opinion>

    Falls back gracefully on malformed output.
    """
    from .social import SocialPost

    stance = "neutral"
    tag = "other"
    confidence = 0.5
    blurb = raw.strip()[:200]
    opinion_after = opinion_before
    parse_ok = True

    try:
        lines = [ln.strip() for ln in raw.strip().splitlines()]
        for line in lines:
            upper = line.upper()
            if upper.startswith("STANCE:"):
                stance = line.split(":", 1)[1].strip().lower()
            elif upper.startswith("TAG:"):
                tag = line.split(":", 1)[1].strip().lower()
            elif upper.startswith("CONFIDENCE:"):
                confidence = float(line.split(":", 1)[1].strip())
            elif upper.startswith("BLURB:"):
                blurb = line.split(":", 1)[1].strip()
        opinion_after = max(-1.0, min(1.0, float(lines[-1])))
    except (ValueError, IndexError):
        # The trailing opinion float is the one field we cannot fake; if it is
        # missing or malformed the response did not follow the format.
        opinion_after = opinion_before
        parse_ok = False

    post = SocialPost(
        agent_id=agent_id,
        archetype=archetype,
        round_number=round_number,
        stance=stance,
        argument_tag=tag,
        confidence=max(0.0, min(1.0, confidence)),
        blurb=blurb,
        opinion_before=opinion_before,
        opinion_after=opinion_after,
        parse_ok=parse_ok,
    )
    return post, opinion_after


def _parse_batch_opinions(raw: str, n: int) -> list[float]:
    opinions: list[float] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            opinions.append(max(-1.0, min(1.0, float(line))))
        except ValueError:
            opinions.append(0.0)
    while len(opinions) < n:
        opinions.append(0.0)
    return opinions[:n]


@runtime_checkable
class LLMProvider(Protocol):
    def get_opinion(
        self, system: str, user_msg: str, model: str, temperature: float | None = None,
    ) -> tuple[float, float]:
        """Return (opinion in [-1, 1], cost_usd >= 0)."""
        ...

    def generate_post(
        self,
        system: str,
        model: str,
        agent_id: str,
        archetype: str,
        round_number: int,
        opinion_before: float,
        temperature: float | None = None,
    ) -> "tuple[SocialPost, float, float]":
        """Return (SocialPost, opinion_after, cost_usd)."""
        ...

    def batch_opinions_from_feed(
        self,
        systems: list[str],
        model: str,
        temperature: float | None = None,
    ) -> tuple[list[float], float]:
        """Return (list of opinion floats, total cost_usd). One opinion per system."""
        ...


class AnthropicProvider:
    def __init__(self, client: Anthropic) -> None:
        self._client = client

    def get_opinion(
        self, system: str, user_msg: str, model: str, temperature: float | None = None,
    ) -> tuple[float, float]:
        kwargs = {"temperature": temperature} if temperature is not None else {}
        response = self._client.messages.create(
            model=model,
            max_tokens=16,
            system=system,
            messages=[{"role": "user", "content": user_msg}],
            **kwargs,
        )
        block = response.content[0]
        text = block.text.strip() if hasattr(block, "text") else ""
        try:
            opinion = max(-1.0, min(1.0, float(text)))
        except ValueError:
            opinion = 0.0
        in_cost, out_cost = _MODEL_COSTS.get(model, _DEFAULT_COSTS)
        cost = response.usage.input_tokens * in_cost + response.usage.output_tokens * out_cost
        return opinion, cost

    def generate_post(self, system, model, agent_id, archetype, round_number, opinion_before,
                       temperature=None):
        kwargs = {"temperature": temperature} if temperature is not None else {}
        response = self._client.messages.create(
            model=model,
            max_tokens=120,
            system=system,
            messages=[{"role": "user", "content": _POST_USER_MSG}],
            **kwargs,
        )
        block = response.content[0]
        raw = block.text.strip() if hasattr(block, "text") else ""
        in_cost, out_cost = _MODEL_COSTS.get(model, _DEFAULT_COSTS)
        cost = response.usage.input_tokens * in_cost + response.usage.output_tokens * out_cost
        post, opinion_after = _parse_post_response(raw, agent_id, archetype, round_number, opinion_before)
        return post, opinion_after, cost

    def batch_opinions_from_feed(self, systems, model, temperature=None):
        if not systems:
            return [], 0.0
        n = len(systems)
        combined = "\n---\n".join(f"Agent {i + 1}:\n{s}" for i, s in enumerate(systems))
        user_msg = _BATCH_USER_SUFFIX.format(n=n)
        kwargs = {"temperature": temperature} if temperature is not None else {}
        response = self._client.messages.create(
            model=model,
            max_tokens=n * 8,
            system=combined,
            messages=[{"role": "user", "content": user_msg}],
            **kwargs,
        )
        block = response.content[0]
        raw = block.text.strip() if hasattr(block, "text") else ""
        in_cost, out_cost = _MODEL_COSTS.get(model, _DEFAULT_COSTS)
        cost = response.usage.input_tokens * in_cost + response.usage.output_tokens * out_cost
        return _parse_batch_opinions(raw, n), cost


class LocalProvider:
    """OpenAI-compatible local inference — Ollama, llama.cpp, vLLM, etc."""

    def __init__(self, base_url: str = _LOCAL_BASE_URL) -> None:
        self._client = openai.OpenAI(
            base_url=base_url,
            api_key="local",
            timeout=_LOCAL_TIMEOUT_SECONDS,
            max_retries=1,
        )

    def _bare(self, model: str) -> str:
        return model.split(":", 1)[-1] if ":" in model else model

    def _complete(self, model: str, system: str, user_msg: str, max_tokens: int,
                   temperature: float | None = None) -> str:
        """
        One bounded completion. Returns "" when the call times out or errors.

        Every caller already handles an unusable response — that is what a
        timeout is — and the existing parse-failure path surfaces it through
        parse_success_rate / low_confidence. Raising instead would kill a
        multi-hour backtest on one slow request from a loaded local server.
        """
        kwargs = {"temperature": temperature} if temperature is not None else {}
        try:
            response = self._client.chat.completions.create(
                model=self._bare(model),
                max_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_msg},
                ],
                **kwargs,
            )
        except Exception:
            return ""
        return (response.choices[0].message.content or "").strip()

    def get_opinion(self, system: str, user_msg: str, model: str,
                     temperature: float | None = None) -> tuple[float, float]:
        text = self._complete(model, system, user_msg, max_tokens=16, temperature=temperature)
        try:
            opinion = max(-1.0, min(1.0, float(text)))
        except ValueError:
            opinion = 0.0
        return opinion, 0.0

    def generate_post(self, system, model, agent_id, archetype, round_number, opinion_before,
                       temperature=None):
        raw = self._complete(model, system, _POST_USER_MSG, max_tokens=120, temperature=temperature)
        post, opinion_after = _parse_post_response(raw, agent_id, archetype, round_number, opinion_before)
        return post, opinion_after, 0.0

    def batch_opinions_from_feed(self, systems, model, temperature=None):
        if not systems:
            return [], 0.0
        n = len(systems)
        combined = "\n---\n".join(f"Agent {i + 1}:\n{s}" for i, s in enumerate(systems))
        raw = self._complete(
            model, combined, _BATCH_USER_SUFFIX.format(n=n), max_tokens=n * 8, temperature=temperature,
        )
        return _parse_batch_opinions(raw, n), 0.0


def make_provider(model: str, base_url: str | None = None) -> LLMProvider:
    """Return AnthropicProvider for Claude models, LocalProvider otherwise."""
    if model.startswith("ollama:") or base_url is not None:
        return LocalProvider(base_url=base_url or _LOCAL_BASE_URL)
    return AnthropicProvider(Anthropic())
