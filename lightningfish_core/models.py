from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ScrapedDocument:
    url: str
    title: str
    content: str
    source: str  # identifier for the enricher that produced this document


@dataclass
class EnrichedSeed:
    domain_id: str
    raw_input: dict
    summary: str
    entities: list[str]
    event_type: str
    metadata: dict
    scraped_context: list[ScrapedDocument] = field(default_factory=list)


@dataclass
class AgentPersona:
    unique_id: str
    archetype: str
    opinion_resistance: float   # 0-1, anchoring strength
    recency_bias: float         # 0-1, weight on most recent signal
    contrarian_tendency: float  # 0-1, inverse-consensus pull
    influence_weight: float     # 0-1, pull on neighbours
    proportion: float           # population share for this archetype
    current_opinion: float = 0.0  # -1 to +1
    herding_coefficient: float = 0.3
    metadata: dict = field(default_factory=dict)


@dataclass
class RoundEvent:
    round_number: int
    opinion_distribution: list[float]
    mean_opinion: float
    stddev_opinion: float
    tier1_calls: int
    active_agent_ids: list[str]
    estimated_cost_usd: float
    social_metrics: object | None = None   # SocialMetrics; typed as object to avoid circular import
    sample_posts: list = field(default_factory=list)


@dataclass
class SimulationResult:
    seed: EnrichedSeed
    trajectory: list[float]         # mean_opinion per round
    round_events: list[RoundEvent]
    final_distribution: list[float]
    total_tier1_calls: int
    total_cost_usd: float
    herding_curve: list[float] = field(default_factory=list)
    argument_timeline: dict[str, int] = field(default_factory=dict)


@dataclass
class GroundTruthRecord:
    data: dict  # domain-specific; each domain casts to its own keys


@dataclass
class BacktestResult:
    direction_match: bool
    magnitude_correlation: float
    domain_metric: dict
    total_tier1_calls: int
    estimated_cost_usd: float
