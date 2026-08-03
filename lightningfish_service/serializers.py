"""
Converts between lightningfish_core dataclasses and plain dicts for JSON transport.
Callables (e.g. resistance_override_fn) are excluded from serialization.
"""
from __future__ import annotations

from lightningfish_core.models import (
    EnrichedSeed,
    RoundEvent,
    ScrapedDocument,
    SimulationResult,
)


def seed_to_dict(seed: EnrichedSeed) -> dict:
    return {
        "domain_id": seed.domain_id,
        "raw_input": seed.raw_input,
        "summary": seed.summary,
        "entities": seed.entities,
        "event_type": seed.event_type,
        "metadata": seed.metadata,
        "scraped_context": [
            {"url": d.url, "title": d.title, "content": d.content, "source": d.source}
            for d in seed.scraped_context
        ],
    }


def seed_from_dict(d: dict) -> EnrichedSeed:
    return EnrichedSeed(
        domain_id=d["domain_id"],
        raw_input=d["raw_input"],
        summary=d["summary"],
        entities=d["entities"],
        event_type=d["event_type"],
        metadata=d["metadata"],
        scraped_context=[
            ScrapedDocument(**doc) for doc in d.get("scraped_context", [])
        ],
    )


def round_event_to_dict(event: RoundEvent) -> dict:
    d: dict = {
        "round_number": event.round_number,
        "mean_opinion": event.mean_opinion,
        "stddev_opinion": event.stddev_opinion,
        "tier1_calls": event.tier1_calls,
        "active_agent_ids": event.active_agent_ids,
        "estimated_cost_usd": event.estimated_cost_usd,
        "opinion_distribution": event.opinion_distribution,
    }
    if event.social_metrics is not None:
        m = event.social_metrics
        d["herding_index"] = m.herding_index
        d["herding_delta"] = m.herding_delta
        d["argument_tags_this_round"] = m.argument_tags_this_round
        d["new_argument_tags"] = m.new_argument_tags
        d["argument_diversity_score"] = m.argument_diversity_score
        d["cascade_detected"] = m.cascade_detected
        d["cascade_trigger_archetype"] = m.cascade_trigger_archetype
        d["settled_fraction"] = m.settled_fraction
        d["parse_success_rate"] = m.parse_success_rate
    d["sample_posts"] = [
        {
            "agent_id": p.agent_id,
            "archetype": p.archetype,
            "stance": p.stance,
            "argument_tag": p.argument_tag,
            "confidence": p.confidence,
            "blurb": p.blurb,
        }
        for p in event.sample_posts
    ]
    return d


def result_to_dict(result: SimulationResult) -> dict:
    return {
        "trajectory": result.trajectory,
        "final_distribution": result.final_distribution,
        "total_tier1_calls": result.total_tier1_calls,
        "total_cost_usd": result.total_cost_usd,
        "seed_summary": result.seed.summary,
        "domain_id": result.seed.domain_id,
        "event_type": result.seed.event_type,
        "herding_curve": result.herding_curve,
        "argument_timeline": result.argument_timeline,
        "mean_parse_success_rate": result.mean_parse_success_rate,
        "low_confidence": result.low_confidence,
    }
