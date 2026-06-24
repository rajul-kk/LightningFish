from lightningfish_coding.personas import build_coding_personas, CIBot
from lightningfish_core.models import EnrichedSeed
from lightningfish_core.rule_agent import RuleBasedAgent


def _seed(ci_pass_rate=None) -> EnrichedSeed:
    return EnrichedSeed(
        "coding", {}, "PR adds auth middleware", [], "feature",
        {"ci_pass_rate": ci_pass_rate},
    )


def test_all_archetypes_present():
    personas = build_coding_personas(200)
    archetypes = {p.archetype for p in personas}
    expected = {
        "SecurityReviewer", "PerformanceReviewer", "StyleMaintainability",
        "DomainExpertMaintainer", "JuniorContributor", "CIBot",
    }
    assert expected == archetypes


def test_cibot_is_rule_based():
    personas = build_coding_personas(100)
    ci_bots = [p for p in personas if p.archetype == "CIBot"]
    assert len(ci_bots) > 0
    assert all(isinstance(b, RuleBasedAgent) for b in ci_bots)


def test_cibot_opinion_from_pass_rate():
    bot = CIBot(
        unique_id="ci1", archetype="CIBot",
        opinion_resistance=0.99, recency_bias=0.99,
        contrarian_tendency=0.0, influence_weight=0.50,
        proportion=0.12,
    )
    assert bot.compute_opinion(_seed(ci_pass_rate=1.0)) == 1.0
    assert bot.compute_opinion(_seed(ci_pass_rate=0.0)) == -1.0
    assert bot.compute_opinion(_seed(ci_pass_rate=0.5)) == 0.0
    assert bot.compute_opinion(_seed(ci_pass_rate=None)) == 0.0


def test_junior_contributor_proportion():
    personas = build_coding_personas(1000)
    juniors = [p for p in personas if p.archetype == "JuniorContributor"]
    assert 350 <= len(juniors) <= 450
