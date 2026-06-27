from __future__ import annotations

from .models import AgentPersona
from .rule_agent import RuleBasedAgent

MAX_TIER1_FRACTION = 0.10


class TierRouter:
    def route(
        self,
        agents: list[AgentPersona],
        active_threshold: float = 0.65,
    ) -> dict[str, list[AgentPersona]]:
        rule_agents = [a for a in agents if isinstance(a, RuleBasedAgent)]
        llm_candidates = [a for a in agents if not isinstance(a, RuleBasedAgent)]

        eligible = [a for a in llm_candidates if a.influence_weight > active_threshold]
        max_active = max(1, int(len(agents) * MAX_TIER1_FRACTION))
        active = sorted(eligible, key=lambda a: a.influence_weight, reverse=True)[:max_active]

        active_ids = {a.unique_id for a in active}
        followers = [a for a in llm_candidates if a.unique_id not in active_ids] + rule_agents

        return {"active": active, "followers": followers}
