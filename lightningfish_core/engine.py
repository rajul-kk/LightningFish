from __future__ import annotations
import statistics
from anthropic import Anthropic
from .models import AgentPersona, EnrichedSeed, RoundEvent, SimulationResult
from .adapter import DomainAdapter
from .tier_router import TierRouter
from .resistance import compute_effective_resistance
from .rule_agent import RuleBasedAgent

_INPUT_COST_PER_TOKEN = 3e-6    # claude-sonnet-4-6: $3/M input tokens
_OUTPUT_COST_PER_TOKEN = 15e-6  # claude-sonnet-4-6: $15/M output tokens


class SimulationEngine:
    def __init__(self, adapter: DomainAdapter, model: str = "claude-sonnet-4-6") -> None:
        self.adapter = adapter
        self.model = model
        self.client = Anthropic()
        self.router = TierRouter()

    def run_streaming(
        self,
        seed: EnrichedSeed,
        agents: list[AgentPersona],
        n_rounds: int,
    ):
        """
        Generator that yields RoundEvent after each round.
        Returns SimulationResult as StopIteration.value when exhausted.

        Usage:
            gen = engine.run_streaming(seed, agents, n_rounds)
            try:
                while True:
                    event = next(gen)
                    # handle event live
            except StopIteration as e:
                result = e.value  # SimulationResult
        """
        trajectory: list[float] = []
        round_events: list[RoundEvent] = []
        total_tier1_calls = 0
        total_cost_usd = 0.0

        for round_num in range(1, n_rounds + 1):
            tiers = self.router.route(agents)
            active = tiers["active"]
            followers = tiers["followers"]

            round_cost = 0.0
            for agent in active:
                opinion, cost = self._llm_opinion(seed, agent)
                agent.current_opinion = opinion
                round_cost += cost

            total_tier1_calls += len(active)
            total_cost_usd += round_cost

            neighbour_pull = (
                statistics.mean(a.current_opinion for a in active) if active else 0.0
            )
            recency_pull = trajectory[-1] if trajectory else 0.0

            for agent in followers:
                if isinstance(agent, RuleBasedAgent):
                    agent.current_opinion = agent.compute_opinion(seed)
                else:
                    effective_r = compute_effective_resistance(
                        agent,
                        social_signal=neighbour_pull,
                        override_fn=agent.metadata.get("resistance_override_fn"),
                    )
                    raw = (
                        agent.current_opinion * effective_r
                        + neighbour_pull * (1 - effective_r) * 0.6
                        + recency_pull * (1 - effective_r) * 0.4
                    )
                    agent.current_opinion = max(-1.0, min(1.0, raw))

            opinions = [a.current_opinion for a in agents]
            mean_op = statistics.mean(opinions)
            stddev_op = statistics.stdev(opinions) if len(opinions) > 1 else 0.0
            trajectory.append(mean_op)

            event = RoundEvent(
                round_number=round_num,
                opinion_distribution=opinions,
                mean_opinion=mean_op,
                stddev_opinion=stddev_op,
                tier1_calls=len(active),
                active_agent_ids=[a.unique_id for a in active],
                estimated_cost_usd=round_cost,
            )
            round_events.append(event)
            yield event

        return SimulationResult(
            seed=seed,
            trajectory=trajectory,
            round_events=round_events,
            final_distribution=[a.current_opinion for a in agents],
            total_tier1_calls=total_tier1_calls,
            total_cost_usd=total_cost_usd,
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
        response = self.client.messages.create(
            model=self.model,
            max_tokens=16,
            system=system,
            messages=[{
                "role": "user",
                "content": (
                    "Output your current opinion as a single float between -1.0 and 1.0. "
                    "Output ONLY the number, nothing else."
                ),
            }],
        )
        text = response.content[0].text.strip()
        try:
            opinion = max(-1.0, min(1.0, float(text)))
        except ValueError:
            opinion = 0.0
        cost = (
            response.usage.input_tokens * _INPUT_COST_PER_TOKEN
            + response.usage.output_tokens * _OUTPUT_COST_PER_TOKEN
        )
        return opinion, cost
