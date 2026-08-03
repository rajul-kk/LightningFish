from __future__ import annotations

import statistics
from collections import Counter

from .adapter import DomainAdapter
from .llm_provider import LLMProvider, make_provider
from .models import AgentPersona, EnrichedSeed, RoundEvent, SimulationResult
from .resistance import blend_opinion
from .rule_agent import RuleBasedAgent
from .social import PostStore, SocialMetrics, SocialPost
from .tier_router import SettledTracker, TierRouter

_T2_USER_MSG = "Output ONLY the number, nothing else."

# Fraction of the T3 herding target drawn from the influence-weighted global
# crowd vs. the agent's own archetype cluster. In-group dominates so echo
# chambers (and bifurcation) can persist, while cross-group contagion still
# exists — the previous code pulled agents only toward their own cluster, so
# archetypes never influenced each other.
_GLOBAL_HERD_WEIGHT = 0.3

# How many times to re-request a T1 post whose structured format failed to parse
# before accepting the fallback opinion (small models drop the format ~half the
# time; a silent fallback reads as false stability).
_MAX_POST_RETRIES = 1

# Mean per-round T1 parse rate below which a run is flagged low-confidence: too
# many silent fallbacks mean the opinions largely reflect format failures.
_MIN_PARSE_RATE = 0.8

# Rounds of movement history required before switching cascade detection from a
# fixed threshold to a z-score against the observed movement distribution.
_CASCADE_MIN_HISTORY = 3
_CASCADE_FALLBACK_THRESHOLD = 0.15
# Absolute floor so a statistically-significant but trivially small blip in mean
# opinion (e.g. 0.005 on a [-1, 1] scale) is not reported as a cascade.
_CASCADE_MIN_MOVE = 0.03


def _cluster_means(agents: list[AgentPersona]) -> dict[str, float]:
    by_arch: dict[str, list[float]] = {}
    for a in agents:
        by_arch.setdefault(a.archetype, []).append(a.current_opinion)
    return {arch: statistics.mean(ops) for arch, ops in by_arch.items()}


def _influence_weighted_mean(agents: list[AgentPersona]) -> float:
    """Global opinion signal, weighted so high-influence agents pull harder."""
    num = sum(a.influence_weight * a.current_opinion for a in agents)
    den = sum(a.influence_weight for a in agents)
    return num / den if den > 1e-9 else 0.0


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
        taxonomy_set = set(taxonomy)
        all_seen_tags: set[str] = set()
        argument_timeline: dict[str, int] = {}
        prev_herding_index = 0.0
        movement_history: list[float] = []

        trajectory: list[float] = []
        herding_curve: list[float] = []
        parse_rates: list[float] = []
        round_events: list[RoundEvent] = []
        total_t1_calls = 0
        total_cost_usd = 0.0

        for round_num in range(1, n_rounds + 1):
            tiers = self.router.route(agents, settled_ids, round_num)
            t1, t2, t3 = tiers["t1"], tiers["t2"], tiers["t3"]
            round_cost = 0.0
            round_posts: list[SocialPost] = []

            # Crowd pressure this round: influence-weighted global mean, snapshotted
            # before any updates so it reflects the state agents are reacting to.
            crowd_signal = _influence_weighted_mean(agents)

            # — T1: generate structured post + updated opinion —
            for agent in t1:
                feed = store.sample_for_feed(agent, round_num)
                viral = store.viral_post(round_num)
                system = self.adapter.post_system_prompt(seed, agent, feed, viral)

                def _gen(a=agent):
                    return self.provider.generate_post(
                        system=system,
                        model=self.model,
                        agent_id=a.unique_id,
                        archetype=a.archetype,
                        round_number=round_num,
                        opinion_before=a.current_opinion,
                    )

                # Retry malformed structured output before accepting the fallback:
                # a dropped post is a silent "no change" that biases the round
                # toward false stability.
                post, llm_opinion, cost = _gen()
                round_cost += cost
                total_t1_calls += 1
                attempts = 0
                while not post.parse_ok and attempts < _MAX_POST_RETRIES:
                    attempts += 1
                    post, llm_opinion, cost = _gen()
                    round_cost += cost
                    total_t1_calls += 1

                # The LLM opinion is a fresh signal, not the final opinion: blend it
                # with the prior through the persona's resistance/recency so those
                # parameters (and the resistance override) actually govern movement.
                override_fn = agent.metadata.get("resistance_override_fn")
                blended = blend_opinion(agent, llm_opinion, crowd_signal, override_fn)
                post.round_number = round_num
                post.opinion_after = blended
                agent.current_opinion = blended
                store.add(post)
                round_posts.append(post)

            total_cost_usd += round_cost

            # — T2: reactors re-evaluate after reading the feed (one call each) —
            for agent in t2:
                feed = store.sample_for_feed(agent, round_num)
                viral = store.viral_post(round_num)
                system = self.adapter.reactor_system_prompt(seed, agent, feed, viral)
                llm_opinion, cost = self.provider.get_opinion(system, _T2_USER_MSG, self.model)
                total_cost_usd += cost
                override_fn = agent.metadata.get("resistance_override_fn")
                agent.current_opinion = blend_opinion(agent, llm_opinion, crowd_signal, override_fn)

            # — T3: herding math (no LLM) —
            # Target blends the influence-weighted global crowd with the agent's own
            # archetype cluster, so groups pull on each other instead of drifting in
            # isolation. contrarian_tendency damps (or, past 1.0, would invert) the pull.
            cluster_means = _cluster_means(agents)
            for agent in t3:
                if isinstance(agent, RuleBasedAgent):
                    agent.current_opinion = agent.compute_opinion(seed)
                else:
                    cluster_mean = cluster_means.get(agent.archetype, 0.0)
                    target = (
                        _GLOBAL_HERD_WEIGHT * crowd_signal
                        + (1.0 - _GLOBAL_HERD_WEIGHT) * cluster_mean
                    )
                    λ = agent.herding_coefficient
                    # Conformists (λ ≥ 0) herd less the more contrarian they are.
                    # Diverging agents (λ < 0) are left intact — applying the same
                    # damping would shrink their divergence toward zero and remove
                    # the force that produces bifurcation.
                    effective_λ = λ * (1.0 - agent.contrarian_tendency) if λ >= 0 else λ
                    raw = (
                        (1.0 - abs(effective_λ)) * agent.current_opinion
                        + effective_λ * target
                    )
                    agent.current_opinion = max(-1.0, min(1.0, raw))

            # — Update settled tracker —
            settled_ids = tracker.update(agents)

            # — Aggregate opinion metrics —
            opinions = [a.current_opinion for a in agents]
            mean_op = statistics.mean(opinions)
            stddev_op = statistics.stdev(opinions) if len(opinions) > 1 else 0.0
            csad = statistics.mean(abs(o - mean_op) for o in opinions)

            # Consensus level normalized against the max attainable dispersion for
            # opinions in [-1, 1] (CSAD_max = 1.0, an even split at the poles).
            # 1 = everyone agrees, 0 = maximally split. No arbitrary round-1 baseline.
            herding_index = 1.0 - csad
            herding_delta = herding_index - prev_herding_index
            prev_herding_index = herding_index

            # — Argument diversity metrics (validated against the taxonomy) —
            round_tags = list({
                (p.argument_tag if p.argument_tag in taxonomy_set else "other")
                for p in round_posts
            })
            valid_tags = {t for t in round_tags if t in taxonomy_set}
            new_tags = [t for t in valid_tags if t not in all_seen_tags]
            for tag in new_tags:
                argument_timeline[tag] = round_num
            all_seen_tags.update(valid_tags)
            ads = len(all_seen_tags) / max(len(taxonomy), 1)  # bounded in [0, 1]

            # — Cascade detection: z-score vs the movement distribution, once we
            #   have enough history; fixed threshold for the first few rounds. —
            prev_mean = trajectory[-1] if trajectory else mean_op
            movement = abs(mean_op - prev_mean)
            if len(movement_history) >= _CASCADE_MIN_HISTORY:
                mu = statistics.mean(movement_history)
                sd = statistics.stdev(movement_history)
                cascade = sd > 1e-9 and movement > mu + 2.0 * sd and movement > _CASCADE_MIN_MOVE
            else:
                cascade = movement > _CASCADE_FALLBACK_THRESHOLD
            movement_history.append(movement)
            trigger = None
            if cascade and round_posts:
                trigger = Counter(p.archetype for p in round_posts).most_common(1)[0][0]

            # — Structured-output health: fraction of T1 posts that parsed cleanly —
            parse_success_rate = (
                sum(1 for p in round_posts if p.parse_ok) / len(round_posts)
                if round_posts else 1.0
            )

            social_metrics = SocialMetrics(
                herding_index=herding_index,
                herding_delta=herding_delta,
                argument_tags_this_round=round_tags,
                new_argument_tags=new_tags,
                argument_diversity_score=ads,
                cascade_detected=cascade,
                cascade_trigger_archetype=trigger,
                settled_fraction=len(settled_ids) / max(len(agents), 1),
                parse_success_rate=parse_success_rate,
            )

            trajectory.append(mean_op)
            herding_curve.append(herding_index)
            parse_rates.append(parse_success_rate)

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

        mean_parse = statistics.mean(parse_rates) if parse_rates else 1.0
        return SimulationResult(
            seed=seed,
            trajectory=trajectory,
            round_events=round_events,
            final_distribution=[a.current_opinion for a in agents],
            total_tier1_calls=total_t1_calls,
            total_cost_usd=total_cost_usd,
            herding_curve=herding_curve,
            argument_timeline=argument_timeline,
            mean_parse_success_rate=mean_parse,
            low_confidence=mean_parse < _MIN_PARSE_RATE,
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
