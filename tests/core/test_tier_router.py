import uuid

from lightningfish_core.models import AgentPersona, EnrichedSeed
from lightningfish_core.rule_agent import RuleBasedAgent
from lightningfish_core.tier_router import TierRouter


def _persona(influence: float, archetype: str = "T") -> AgentPersona:
    return AgentPersona(
        unique_id=str(uuid.uuid4()), archetype=archetype,
        opinion_resistance=0.5, recency_bias=0.5,
        contrarian_tendency=0.2, influence_weight=influence,
        proportion=0.1,
    )


class ConcreteRuleAgent(RuleBasedAgent):
    def compute_opinion(self, seed: EnrichedSeed) -> float:
        return 1.0


def test_high_influence_agents_become_active():
    # 25 agents: 10% cap = 2, so both high-influence agents should be active
    router = TierRouter()
    agents = [_persona(0.9), _persona(0.9)] + [_persona(0.3) for _ in range(23)]
    result = router.route(agents)
    assert len(result["active"]) == 2
    assert len(result["followers"]) == 23


def test_tier1_hard_cap_enforced():
    router = TierRouter()
    agents = [_persona(0.9) for _ in range(20)]
    result = router.route(agents)
    assert len(result["active"]) <= max(1, int(20 * 0.10))


def test_rule_based_agents_always_go_to_followers():
    router = TierRouter()
    rule_agent = ConcreteRuleAgent(
        unique_id=str(uuid.uuid4()), archetype="CI",
        opinion_resistance=0.99, recency_bias=0.99,
        contrarian_tendency=0.0, influence_weight=0.99,
        proportion=0.1,
    )
    regular = _persona(0.9)
    result = router.route([rule_agent, regular])
    follower_ids = {a.unique_id for a in result["followers"]}
    assert rule_agent.unique_id in follower_ids


def test_active_plus_followers_equals_total():
    router = TierRouter()
    agents = [_persona(0.9 if i < 5 else 0.3) for i in range(20)]
    result = router.route(agents)
    assert len(result["active"]) + len(result["followers"]) == 20
