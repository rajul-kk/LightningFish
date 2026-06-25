import uuid
import pytest
from unittest.mock import MagicMock, patch
from lightningfish_core.engine import SimulationEngine
from lightningfish_core.backtest_base import BacktestHarness
from lightningfish_core.models import (
    AgentPersona, EnrichedSeed, SimulationResult, BacktestResult, GroundTruthRecord,
)
from lightningfish_core.adapter import DomainAdapter


def _seed() -> EnrichedSeed:
    return EnrichedSeed("test", {}, "Test event", [], "other", {})


def _persona(influence: float) -> AgentPersona:
    return AgentPersona(
        unique_id=str(uuid.uuid4()), archetype="T",
        opinion_resistance=0.5, recency_bias=0.5,
        contrarian_tendency=0.2, influence_weight=influence,
        proportion=0.1,
    )


class StubAdapter(DomainAdapter):
    domain_id = "stub"
    display_name = "Stub"
    opinion_labels = ("no", "yes")
    def enrich_seed(self, r): return _seed()
    def build_personas(self, n): return [_persona(0.9) for _ in range(n)]
    def agent_system_prompt(self, seed, persona): return "You are a test agent."
    def get_ground_truth(self, seed): return None
    def score(self, result, truth): return BacktestResult(True, 0.5, {}, 0, 0.0)


def _mock_anthropic(opinion_text: str = "0.4"):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=opinion_text)]
    mock_response.usage.input_tokens = 100
    mock_response.usage.output_tokens = 10
    mock_client.messages.create.return_value = mock_response
    return mock_client


def test_engine_returns_simulation_result():
    agents = [_persona(0.9 if i < 2 else 0.3) for i in range(20)]
    with patch("lightningfish_core.llm_provider.Anthropic") as mock_cls:
        mock_cls.return_value = _mock_anthropic()
        engine = SimulationEngine(StubAdapter())
        result = engine.run(_seed(), agents, n_rounds=3)

    assert isinstance(result, SimulationResult)
    assert len(result.trajectory) == 3
    assert len(result.round_events) == 3


def test_tier1_calls_capped():
    agents = [_persona(0.9) for _ in range(50)]
    with patch("lightningfish_core.llm_provider.Anthropic") as mock_cls:
        mock_cls.return_value = _mock_anthropic()
        engine = SimulationEngine(StubAdapter())
        result = engine.run(_seed(), agents, n_rounds=2)

    for event in result.round_events:
        assert event.tier1_calls <= max(1, int(50 * 0.10))


def test_opinions_clamped():
    agents = [_persona(0.3) for _ in range(10)]
    with patch("lightningfish_core.llm_provider.Anthropic") as mock_cls:
        mock_cls.return_value = _mock_anthropic("5.0")  # out-of-range LLM output
        engine = SimulationEngine(StubAdapter())
        result = engine.run(_seed(), agents, n_rounds=1)

    for op in result.final_distribution:
        assert -1.0 <= op <= 1.0


def test_engine_uses_local_provider_for_ollama_model():
    """Engine with ollama: model should use LocalProvider — no Anthropic calls, zero cost."""
    agents = [_persona(0.9 if i < 2 else 0.3) for i in range(20)]
    with patch("lightningfish_core.llm_provider.openai.OpenAI") as mock_cls:
        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock(message=MagicMock(content="0.3"))]
        mock_cls.return_value.chat.completions.create.return_value = mock_completion
        engine = SimulationEngine(
            StubAdapter(), model="ollama:llama3.2", base_url="http://localhost:11434/v1"
        )
        result = engine.run(_seed(), agents, n_rounds=2)
    assert result.total_cost_usd == pytest.approx(0.0)
    assert len(result.trajectory) == 2


class StubHarness(BacktestHarness):
    def get_seed_events(self):
        return [_seed()]


def test_backtest_harness_raises_when_no_ground_truth():
    with patch("lightningfish_core.llm_provider.Anthropic") as mock_cls:
        mock_cls.return_value = _mock_anthropic()
        harness = StubHarness(StubAdapter())
        with pytest.raises(ValueError, match="Ground truth not available"):
            harness.run(_seed(), n_agents=20, n_rounds=2)
