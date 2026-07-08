from __future__ import annotations

import statistics
from collections import Counter

from .adapter import DomainAdapter
from .llm_provider import LLMProvider, make_provider
from .models import AgentPersona, EnrichedSeed, RoundEvent, SimulationResult
from .rule_agent import RuleBasedAgent
from .social import PostStore, SocialMetrics
from .tier_router import SettledTracker, TierRouter

_T2_USER_MSG = (
    "Based on the posts you have read and your own analysis, "
    "output your updated opinion as a single float between -1.0 and 1.0. "
    "Output ONLY the number, nothing else."
)


def _cluster_means(agents: list[AgentPersona]) -> dict[str, float]:
    by_arch: dict[str, list[float]] = {}
    for a in agents:
        by_arch.setdefault(a.archetype, []).append(a.current_opinion)
    return {arch: statistics.mean(ops) for arch, ops in by_arch.items()}


class SimulationEngine:
    def __init__(
        self,
        adapter: DomainAdapter,
        model: str = "claude-sonnet-4-6",
        base_url: str | None = None,
    ) -> None:
        self.adapter = adapter
        self.model = model
        self.provider: LLMProvider = make_provider(model, base_url)
        self.router = TierRouter()

    def run_streaming(
        self,
        seed: EnrichedSeed,
        agents: list[AgentPersona],
        n_rounds: int,
    ):
        """
        Generator yielding RoundEvent after each round.
        Returns SimulationResult as StopIteration.value when exhausted.

        Usage:
            gen = engine.run_streaming(seed, agents, n_rounds)
            try:
                while True:
                    event = next(gen)
            except StopIteration as e:
                result = e.value
        """
        store = PostStore()
        tracker = SettledTracker()
        settled_ids: set[str] = set()
        taxonomy = self.adapter.argument_taxonomy()
        all_seen_tags: set[str] = set()
        argument_timeline: dict[str, int] = {}
        initial_csad: float | None = None
        prev_herding_index = 0.0

        trajectory: list[float] = []
        herding_curve: list[float] = []
        round_events: list[RoundEvent] = []
        total_t1_calls = 0
        total_cost_usd = 0.0

        for round_num in range(1, n_rounds + 1):
            tiers = self.router.route(agents, settled_ids, round_num)
            t1, t2, t3 = tiers["t1"], tiers["t2"], tiers["t3"]
            round_cost = 0.0
            round_posts = []

            # — T1: generate structured post + updated opinion —
            for agent in t1:
                feed = store.sample_for_feed(agent, round_num)
                viral = store.viral_post(round_num)
                system = self.adapter.post_system_prompt(seed, agent, feed, viral)
                post, opinion_after, cost = self.provider.generate_post(
                    system=system,
                    model=self.model,
                    agent_id=agent.unique_id,
                    archetype=agent.archetype,
                    round_number=round_num,
                    opinion_before=agent.current_opinion,
                )
                post.round_number = round_num
                agent.current_opinion = opinion_after
                store.add(post)
                round_posts.append(post)
                round_cost += cost

            total_t1_calls += len(t1)
            total_cost_usd += round_cost

            # — T2: batched opinion update from feed —
            if t2:
                t2_systems = [
                    self.adapter.agent_system_prompt(seed, agent)
                    for agent in t2
                ]
                t2_opinions, t2_cost = self.provider.batch_opinions_from_feed(t2_systems, self.model)
                total_cost_usd += t2_cost
                for agent, opinion in zip(t2, t2_opinions):
                    agent.current_opinion = opinion

            # — T3: herding math (no LLM) —
            cluster_means = _cluster_means(agents)
            recency_pull = trajectory[-1] if trajectory else 0.0
            for agent in t3:
                if isinstance(agent, RuleBasedAgent):
                    agent.current_opinion = agent.compute_opinion(seed)
                else:
                    cluster_mean = cluster_means.get(agent.archetype, 0.0)
                    λ = agent.herding_coefficient
                    effective_λ = λ * (1.0 - agent.contrarian_tendency)
                    raw = (
                        (1.0 - abs(effective_λ)) * agent.current_opinion
                        + effective_λ * cluster_mean
                    )
                    agent.current_opinion = max(-1.0, min(1.0, raw))

            # — Update settled tracker —
            settled_ids = tracker.update(agents)

            # — Aggregate opinion metrics —
            opinions = [a.current_opinion for a in agents]
            mean_op = statistics.mean(opinions)
            stddev_op = statistics.stdev(opinions) if len(opinions) > 1 else 0.0
            csad = statistics.mean(abs(o - mean_op) for o in opinions)

            if initial_csad is None:
                initial_csad = csad if csad > 1e-9 else 1e-9
            herding_index = 1.0 - csad / initial_csad
            herding_delta = herding_index - prev_herding_index
            prev_herding_index = herding_index

            # — Argument diversity metrics —
            round_tags = list({p.argument_tag for p in round_posts})
            new_tags = [t for t in round_tags if t not in all_seen_tags]
            for tag in new_tags:
                argument_timeline[tag] = round_num
            all_seen_tags.update(round_tags)
            ads = len(all_seen_tags) / max(len(taxonomy), 1)

            # — Cascade detection —
            prev_mean = trajectory[-1] if trajectory else mean_op
            cascade = abs(mean_op - prev_mean) > 0.15
            trigger = None
            if cascade and round_posts:
                trigger = Counter(p.archetype for p in round_posts).most_common(1)[0][0]

            social_metrics = SocialMetrics(
                herding_index=herding_index,
                herding_delta=herding_delta,
                argument_tags_this_round=round_tags,
                new_argument_tags=new_tags,
                argument_diversity_score=ads,
                cascade_detected=cascade,
                cascade_trigger_archetype=trigger,
                settled_fraction=len(settled_ids) / max(len(agents), 1),
            )

            trajectory.append(mean_op)
            herding_curve.append(herding_index)

            event = RoundEvent(
                round_number=round_num,
                opinion_distribution=opinions,
                mean_opinion=mean_op,
                stddev_opinion=stddev_op,
                tier1_calls=len(t1),
                active_agent_ids=[a.unique_id for a in t1],
                estimated_cost_usd=round_cost,
                social_metrics=social_metrics,
                sample_posts=round_posts[:5],
            )
            round_events.append(event)
            yield event

        return SimulationResult(
            seed=seed,
            trajectory=trajectory,
            round_events=round_events,
            final_distribution=[a.current_opinion for a in agents],
            total_tier1_calls=total_t1_calls,
            total_cost_usd=total_cost_usd,
            herding_curve=herding_curve,
            argument_timeline=argument_timeline,
        )

    def run(
        self,
        seed: EnrichedSeed,
        agents: list[AgentPersona],
        n_rounds: int,
    ) -> SimulationResult:
        gen = self.run_streaming(seed, agents, n_rounds)
        try:
            while True:
                next(gen)
        except StopIteration as e:
            return e.value

    def _llm_opinion(self, seed: EnrichedSeed, agent: AgentPersona) -> tuple[float, float]:
        system = self.adapter.agent_system_prompt(seed, agent)
        return self.provider.get_opinion(system, "Output ONLY the number.", self.model)
