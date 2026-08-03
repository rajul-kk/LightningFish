from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from .models import AgentPersona, BacktestResult, EnrichedSeed, GroundTruthRecord, SimulationResult

if TYPE_CHECKING:
    from .social import SocialPost


class DomainAdapter(ABC):
    domain_id: str
    display_name: str
    opinion_labels: tuple[str, str]  # (negative_pole, positive_pole)

    @abstractmethod
    def enrich_seed(self, raw_input: dict) -> EnrichedSeed: ...

    @abstractmethod
    def build_personas(
        self,
        n_agents: int,
        archetype_config: dict[str, float] | None = None,
    ) -> list[AgentPersona]: ...

    @abstractmethod
    def agent_system_prompt(self, seed: EnrichedSeed, persona: AgentPersona) -> str: ...

    @abstractmethod
    def get_ground_truth(self, seed: EnrichedSeed) -> GroundTruthRecord | None: ...

    @abstractmethod
    def score(self, result: SimulationResult, truth: GroundTruthRecord) -> BacktestResult: ...

    def naive_prediction(self, seed: EnrichedSeed) -> float:
        """
        A trivial, LLM-free directional prediction for the backtest baseline
        (return value in [-1, 1]; sign is what matters). The simulation has to
        beat this to justify its cost. Default: no opinion. Domains override.
        """
        return 0.0

    def truth_direction(self, truth: GroundTruthRecord) -> int:
        """
        The actual outcome's direction: +1, -1, or 0 (no directional signal).
        Events returning 0 are skipped by the backtest. Domains override.
        """
        return 0

    def baseline_llm_prompt(self, seed: EnrichedSeed) -> str:
        """
        One-shot prompt for the 'single_llm' backtest baseline: ask the model
        for a directional call in a single call, with no agents or rounds. The
        multi-agent sim must beat this to justify its extra cost.
        """
        neg, pos = self.opinion_labels
        return (
            f"Event: {seed.summary}\n\n"
            f"Predict the outcome as a single float between -1.0 ({neg}) and "
            f"1.0 ({pos}). Output ONLY the number."
        )

    @abstractmethod
    def argument_taxonomy(self) -> list[str]:
        """Return the ordered list of argument tags for this domain (exactly 8 items)."""
        ...

    @abstractmethod
    def post_system_prompt(
        self,
        seed: EnrichedSeed,
        persona: AgentPersona,
        feed: "list[SocialPost]",
        viral: "SocialPost | None",
    ) -> str:
        """
        System prompt for T1 (originator) agents.
        The LLM must respond in this constrained format:
            STANCE: <positive_label|negative_label>
            TAG: <one tag from argument_taxonomy()>
            CONFIDENCE: <float 0.0-1.0>
            BLURB: <one sentence ≤60 words>
            <float opinion -1.0 to 1.0>
        """
        ...

    def reactor_system_prompt(
        self,
        seed: EnrichedSeed,
        persona: AgentPersona,
        feed: "list[SocialPost]",
        viral: "SocialPost | None",
    ) -> str:
        """
        System prompt for T2 (reactor) agents: the base agent prompt plus the
        social feed the agent has seen, asking for a single updated float.

        T2 agents do not author structured posts, but — unlike a bare opinion
        re-evaluation — they must actually see what the crowd is saying. Domains
        may override this; the default appends the feed to ``agent_system_prompt``.
        """
        base = self.agent_system_prompt(seed, persona)
        if not feed and viral is None:
            return base
        lines = [f"  [{p.archetype}] [{p.argument_tag}] {p.blurb}" for p in feed]
        feed_block = ""
        if lines:
            feed_block += "Recent posts you have seen:\n" + "\n".join(lines) + "\n\n"
        if viral is not None:
            feed_block += (
                f"Trending post (high confidence): [{viral.archetype}] "
                f"[{viral.argument_tag}] {viral.blurb}\n\n"
            )
        return (
            f"{base}\n\n{feed_block}"
            "Reconsider your opinion in light of these posts. Output ONLY the number."
        )
