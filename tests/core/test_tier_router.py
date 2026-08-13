import uuid

from lightningfish_core.models import AgentPersona, EnrichedSeed
from lightningfish_core.rule_agent import RuleBasedAgent
from lightningfish_core.tier_router import SettledTracker, TierRouter


def _persona(influence: float, opinion: float = 0.0, archetype: str = "T") -> AgentPersona:
    return AgentPersona(
        unique_id=str(uuid.uuid4()), archetype=archetype,
        opinion_resistance=0.5, recency_bias=0.5,
        contrarian_tendency=0.2, influence_weight=influence,
        proportion=0.1,
        current_opinion=opinion,
    )


class ConcreteRuleAgent(RuleBasedAgent):
    def compute_opinion(self, seed: EnrichedSeed) -> float:
        return 1.0


# — existing behaviour preserved with new API —

def test_high_influence_agents_go_to_t1():
    router = TierRouter()
    agents = [_persona(0.9), _persona(0.9)] + [_persona(0.3) for _ in range(23)]
    result = router.route(agents, settled_ids=set(), round_number=1)
    assert len(result["t1"]) == 2


def test_t1_hard_cap_enforced():
    router = TierRouter()
    agents = [_persona(0.9) for _ in range(20)]
    result = router.route(agents, settled_ids=set(), round_number=1)
    assert len(result["t1"]) <= max(1, int(20 * 0.10))


def test_rule_based_agents_go_to_t3():
    router = TierRouter()
    rule_agent = ConcreteRuleAgent(
        unique_id=str(uuid.uuid4()), archetype="CI",
        opinion_resistance=0.99, recency_bias=0.99,
        contrarian_tendency=0.0, influence_weight=0.99,
        proportion=0.1,
    )
    regular = _persona(0.9)
    result = router.route([rule_agent, regular], settled_ids=set(), round_number=1)
    t3_ids = {a.unique_id for a in result["t3"]}
    assert rule_agent.unique_id in t3_ids


def test_t1_plus_t2_plus_t3_equals_total():
    router = TierRouter()
    agents = [_persona(0.9 if i < 5 else 0.3) for i in range(20)]
    result = router.route(agents, settled_ids=set(), round_number=1)
    assert len(result["t1"]) + len(result["t2"]) + len(result["t3"]) == 20


# — new T2 and SettledTracker tests —

def test_route_returns_t1_t2_t3_keys():
    router = TierRouter()
    agents = [_persona(0.9), _persona(0.5), _persona(0.3, opinion=0.1)]
    result = router.route(agents, settled_ids=set(), round_number=1)
    assert set(result.keys()) == {"t1", "t2", "t3"}


def test_t2_agents_are_uncertain():
    router = TierRouter()
    agents = [_persona(0.95), _persona(0.90)] + [_persona(0.3, opinion=0.05) for _ in range(18)]
    result = router.route(agents, settled_ids=set(), round_number=1)
    for a in result["t2"]:
        assert abs(a.current_opinion) < 0.4


def test_settled_agents_go_to_t3():
    router = TierRouter()
    agents = [_persona(0.95), _persona(0.85)]
    settled = {agents[0].unique_id}
    result = router.route(agents, settled_ids=settled, round_number=1)
    t1_ids = {a.unique_id for a in result["t1"]}
    assert agents[0].unique_id not in t1_ids
    t3_ids = {a.unique_id for a in result["t3"]}
    assert agents[0].unique_id in t3_ids


def test_t2_selection_is_not_biased_by_construction_order():
    # Regression: eligible_t2[:max_t2] silently favored whichever archetype was
    # listed first in the agents list (i.e. first in a domain's persona config),
    # every round, for the whole simulation — not a random or representative
    # sample. 40 agents of archetype "First" followed by 40 of "Second", all
    # equally eligible for T2; over many independent routings the two
    # archetypes should get roughly equal representation, not "First" always
    # winning every slot.
    router = TierRouter()
    agents = (
        [_persona(0.3, opinion=0.05, archetype="First") for _ in range(40)]
        + [_persona(0.3, opinion=0.05, archetype="Second") for _ in range(40)]
    )
    first_count = 0
    second_count = 0
    for _ in range(30):
        result = router.route(agents, settled_ids=set(), round_number=1)
        for a in result["t2"]:
            if a.archetype == "First":
                first_count += 1
            else:
                second_count += 1
    assert second_count > 0, "Second' archetype never got a single T2 slot across 30 routings"


def test_t2_capped_at_20_percent():
    router = TierRouter()
    agents = [_persona(0.3, opinion=0.05) for _ in range(100)]
    result = router.route(agents, settled_ids=set(), round_number=1)
    assert len(result["t2"]) <= 20


def test_settled_tracker_marks_stable_agents():
    tracker = SettledTracker(threshold=0.03, patience=2)
    agent = _persona(0.5, opinion=0.5)
    tracker.update([agent])
    agent.current_opinion = 0.501
    tracker.update([agent])
    settled = tracker.update([agent])
    assert agent.unique_id in settled


def test_settled_tracker_resets_on_large_change():
    tracker = SettledTracker(threshold=0.03, patience=2)
    agent = _persona(0.5, opinion=0.5)
    tracker.update([agent])
    agent.current_opinion = 0.501
    tracker.update([agent])
    agent.current_opinion = 0.8
    settled = tracker.update([agent])
    assert agent.unique_id not in settled


def test_settled_tracker_returns_set():
    tracker = SettledTracker()
    agent = _persona(0.5)
    result = tracker.update([agent])
    assert isinstance(result, set)
