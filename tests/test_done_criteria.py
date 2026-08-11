"""
Automated verification of the six done criteria from the spec.
These run without live API calls — structural properties only.
"""
import statistics

from lightningfish_coding.personas import build_coding_personas
from lightningfish_core.tier_router import TierRouter
from lightningfish_finance.personas import build_finance_personas
from lightningfish_hn.personas import build_hn_personas


def test_core_contains_no_domain_specific_strings():
    import os
    core_dir = os.path.join(os.path.dirname(__file__), "..", "lightningfish_core")
    banned = [
        "finance", "coding", "ticker", "reddit", "github", "pull_request",
        "filing", "algolia",
    ]
    for root, _dirs, files in os.walk(core_dir):
        for fname in files:
            if not fname.endswith(".py"):
                continue
            path = os.path.join(root, fname)
            text = open(path).read().lower()
            for term in banned:
                assert term not in text, (
                    f"Domain-specific string '{term}' found in {path}"
                )


def test_tier1_hard_cap_all_domains():
    router = TierRouter()
    for n in [100, 500, 1000]:
        finance_agents = build_finance_personas(n)
        tiers = router.route(finance_agents, settled_ids=set(), round_number=1)
        assert len(tiers["t1"]) / n <= 0.10 + 1e-9, f"Finance cap violated at n={n}"

        coding_agents = build_coding_personas(n)
        tiers = router.route(coding_agents, settled_ids=set(), round_number=1)
        assert len(tiers["t1"]) / n <= 0.10 + 1e-9, f"Coding cap violated at n={n}"

        hn_agents = build_hn_personas(n)
        tiers = router.route(hn_agents, settled_ids=set(), round_number=1)
        assert len(tiers["t1"]) / n <= 0.10 + 1e-9, f"HN cap violated at n={n}"


def test_finance_archetype_parameter_diversity():
    personas = build_finance_personas(500)
    resistances = [p.opinion_resistance for p in personas]
    assert statistics.stdev(resistances) > 0.1


def test_coding_archetype_parameter_diversity():
    personas = build_coding_personas(500)
    resistances = [p.opinion_resistance for p in personas]
    assert statistics.stdev(resistances) > 0.1


def test_hn_archetype_parameter_diversity():
    personas = build_hn_personas(500)
    resistances = [p.opinion_resistance for p in personas]
    assert statistics.stdev(resistances) > 0.1


def test_all_domains_register():
    import lightningfish_coding  # noqa: F401
    import lightningfish_finance  # noqa: F401
    import lightningfish_hn  # noqa: F401
    from lightningfish_core.registry import registry
    assert registry.get("finance") is not None
    assert registry.get("coding") is not None
    assert registry.get("hn") is not None
