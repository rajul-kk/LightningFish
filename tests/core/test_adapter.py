import pytest

from lightningfish_core.adapter import DomainAdapter
from lightningfish_core.enricher import EnricherPlugin
from lightningfish_core.models import AgentPersona
from lightningfish_core.rule_agent import RuleBasedAgent


def test_domain_adapter_is_abstract():
    with pytest.raises(TypeError):
        DomainAdapter()


def test_enricher_plugin_is_abstract():
    with pytest.raises(TypeError):
        EnricherPlugin()


def test_rule_based_agent_is_subclass_of_agent_persona():
    assert issubclass(RuleBasedAgent, AgentPersona)


def test_concrete_adapter_must_implement_all_methods():
    class Incomplete(DomainAdapter):
        domain_id = "test"
        display_name = "Test"
        opinion_labels = ("no", "yes")
        def enrich_seed(self, raw_input): ...
        # missing build_personas, agent_system_prompt, get_ground_truth, score

    with pytest.raises(TypeError):
        Incomplete()
