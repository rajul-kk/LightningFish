import pytest

from lightningfish_core.adapter import DomainAdapter
from lightningfish_core.models import BacktestResult, EnrichedSeed
from lightningfish_core.registry import DomainRegistry


class MockAdapter(DomainAdapter):
    domain_id = "mock"
    display_name = "Mock Domain"
    opinion_labels = ("no", "yes")
    def enrich_seed(self, raw_input): return EnrichedSeed("mock", {}, "", [], "other", {})
    def build_personas(self, n): return []
    def agent_system_prompt(self, seed, persona): return ""
    def get_ground_truth(self, seed): return None
    def score(self, result, truth): return BacktestResult(False, 0.0, {}, 0, 0.0)


def test_register_and_get():
    reg = DomainRegistry()
    adapter = MockAdapter()
    reg.register(adapter)
    assert reg.get("mock") is adapter


def test_get_unknown_raises():
    reg = DomainRegistry()
    with pytest.raises(KeyError):
        reg.get("unknown")


def test_all_returns_list():
    reg = DomainRegistry()
    reg.register(MockAdapter())
    assert len(reg.all()) == 1
