from __future__ import annotations
import math
from scipy.stats import pearsonr
from lightningfish_core.adapter import DomainAdapter
from lightningfish_core.models import (
    EnrichedSeed, AgentPersona, GroundTruthRecord, SimulationResult, BacktestResult,
)
from .personas import build_finance_personas
from .seed_enricher import enrich_finance_seed
from .ground_truth import get_finance_ground_truth


class FinanceDomainAdapter(DomainAdapter):
    domain_id = "finance"
    display_name = "Market Sentiment"
    opinion_labels = ("bearish", "bullish")

    def enrich_seed(self, raw_input: dict) -> EnrichedSeed:
        return enrich_finance_seed(
            raw_input["ticker"],
            raw_input["filing_text"],
            raw_input["filing_date"],
        )

    def build_personas(self, n_agents: int) -> list[AgentPersona]:
        return build_finance_personas(n_agents)

    def agent_system_prompt(self, seed: EnrichedSeed, persona: AgentPersona) -> str:
        return (
            f"You are a {persona.archetype} investor.\n\n"
            f"Event context:\n{seed.summary}\n\n"
            f"Your characteristics:\n"
            f"- Opinion resistance (anchoring): {persona.opinion_resistance} (1=never changes mind)\n"
            f"- Recency bias: {persona.recency_bias} (1=very reactive to recent news)\n"
            f"- Contrarian tendency: {persona.contrarian_tendency} (1=bets against consensus)\n"
            f"- Current opinion: {persona.current_opinion:.2f} (-1=very bearish, +1=very bullish)\n\n"
            f"Based on this 8-K filing and your investment style, output your updated opinion as a "
            f"single float between -1.0 (very bearish) and 1.0 (very bullish). Output ONLY the number."
        )

    def get_ground_truth(self, seed: EnrichedSeed) -> GroundTruthRecord | None:
        filing_date = seed.metadata.get("filing_date")
        if not filing_date:
            return None
        return get_finance_ground_truth(seed.metadata["ticker"], filing_date)

    def score(self, result: SimulationResult, truth: GroundTruthRecord) -> BacktestResult:
        sentiment = truth.data["sentiment_series"]
        price_change_pct = truth.data["price_change_pct"]

        direction_match = bool(
            (result.trajectory[-1] > 0) == (sentiment[-1] > 0)
        ) if sentiment else False

        n = min(len(result.trajectory), len(sentiment))
        if n >= 2:
            corr, _ = pearsonr(result.trajectory[:n], sentiment[:n])
            magnitude_correlation = 0.0 if math.isnan(corr) else float(corr)
        else:
            magnitude_correlation = 0.0

        return BacktestResult(
            direction_match=direction_match,
            magnitude_correlation=magnitude_correlation,
            domain_metric={
                "price_direction_match": (result.trajectory[-1] > 0) == (price_change_pct > 0),
                "price_change_pct": price_change_pct,
            },
            total_tier1_calls=result.total_tier1_calls,
            estimated_cost_usd=result.total_cost_usd,
        )
