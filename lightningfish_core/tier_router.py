from __future__ import annotations

from .models import AgentPersona
from .rule_agent import RuleBasedAgent

MAX_T1_FRACTION = 0.10
MAX_T2_FRACTION = 0.20
T1_INFLUENCE_THRESHOLD = 0.65
T2_UNCERTAINTY_THRESHOLD = 0.40   # |opinion| below this → eligible for T2


class SettledTracker:
    """Tracks agents whose opinions have stopped meaningfully changing."""

    def __init__(self, threshold: float = 0.03, patience: int = 2) -> None:
        self._threshold = threshold
        self._patience = patience
        self._prev: dict[str, float] = {}
        self._stable_rounds: dict[str, int] = {}
        self._settled: set[str] = set()

    def update(self, agents: list[AgentPersona]) -> set[str]:
        for agent in agents:
            uid = agent.unique_id
            if uid in self._settled:
                continue
            prev = self._prev.get(uid)
            if prev is not None and abs(agent.current_opinion - prev) < self._threshold:
                self._stable_rounds[uid] = self._stable_rounds.get(uid, 0) + 1
                if self._stable_rounds[uid] >= self._patience:
                    self._settled.add(uid)
            else:
                self._stable_rounds[uid] = 0
            self._prev[uid] = agent.current_opinion
        return set(self._settled)


class TierRouter:
    def route(
        self,
        agents: list[AgentPersona],
        settled_ids: set[str] | None = None,
        round_number: int = 1,
    ) -> dict[str, list[AgentPersona]]:
        """
        Split agents into three tiers:
          t1 — originators: top influence_weight, not settled, not rule-based (max 10%)
          t2 — reactors: uncertain opinion, not T1, not settled, not rule-based (max 20%)
          t3 — drifters: everyone else (settled, committed, rule-based)
        """
        if settled_ids is None:
            settled_ids = set()

        rule_agents = [a for a in agents if isinstance(a, RuleBasedAgent)]
        llm_agents = [a for a in agents if not isinstance(a, RuleBasedAgent)]

        # T1: high-influence, not settled
        eligible_t1 = [
            a for a in llm_agents
            if a.influence_weight > T1_INFLUENCE_THRESHOLD and a.unique_id not in settled_ids
        ]
        max_t1 = max(1, int(len(agents) * MAX_T1_FRACTION))
        t1 = sorted(eligible_t1, key=lambda a: a.influence_weight, reverse=True)[:max_t1]
        t1_ids = {a.unique_id for a in t1}

        # T2: uncertain (|opinion| < threshold), not settled, not in T1
        eligible_t2 = [
            a for a in llm_agents
            if abs(a.current_opinion) < T2_UNCERTAINTY_THRESHOLD
            and a.unique_id not in settled_ids
            and a.unique_id not in t1_ids
        ]
        max_t2 = max(1, int(len(agents) * MAX_T2_FRACTION))
        t2 = eligible_t2[:max_t2]
        t2_ids = {a.unique_id for a in t2}

        # T3: everyone else
        t3_llm = [a for a in llm_agents if a.unique_id not in t1_ids and a.unique_id not in t2_ids]
        t3 = t3_llm + rule_agents

        return {"t1": t1, "t2": t2, "t3": t3}
