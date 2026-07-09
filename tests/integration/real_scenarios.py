"""
Real-world scenario catalog for Lightningfish social simulation.

Each scenario is designed to exploit specific archetype interactions and
produce a distinct social dynamic. Run with a real ANTHROPIC_API_KEY:

    python -m tests.integration.real_scenarios [scenario_id]

If no scenario_id given, lists all scenarios and exits.

Requirements:
    ANTHROPIC_API_KEY   — set in environment
    GITHUB_TOKEN        — required only for coding scenarios
"""
from __future__ import annotations

import io
import os
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from dataclasses import dataclass

from lightningfish_core.engine import SimulationEngine
from lightningfish_core.models import EnrichedSeed, RoundEvent, SimulationResult

_RESET   = "\033[0m"
_BOLD    = "\033[1m"
_DIM     = "\033[2m"
_GREEN   = "\033[32m"
_RED     = "\033[31m"
_YELLOW  = "\033[33m"
_CYAN    = "\033[36m"


# ── Scenario definition ───────────────────────────────────────────────────────

@dataclass
class Scenario:
    id: str
    title: str
    domain: str
    seed_kwargs: dict          # passed to EnrichedSeed or to adapter.enrich_seed
    use_enricher: bool         # True = call adapter.enrich_seed(seed_kwargs["raw_input"])
    n_agents: int
    n_rounds: int
    archetype_config: dict[str, float] | None
    expected_dynamic: str      # one of: herd / cascade / bifurcation / uncertain
    why: str                   # mechanism explanation
    archetype_drivers: str     # which archetypes drive the interesting behaviour


# ── Finance scenarios ─────────────────────────────────────────────────────────

_SCENARIOS: list[Scenario] = [

    Scenario(
        id="fin-1",
        title="SMCI: Earnings beat, accounting scandal breaks",
        domain="finance",
        use_enricher=False,
        seed_kwargs=dict(
            domain_id="finance",
            raw_input={"ticker": "SMCI"},
            summary=(
                "Super Micro Computer (SMCI) posted record revenue of $5.3B (+143% YoY) beating estimates. "
                "However, short-seller Hindenburg Research released a report alleging accounting "
                "irregularities, channel-stuffing, and undisclosed related-party transactions. "
                "Auditor Ernst & Young resigned mid-engagement citing inability to rely on management. "
                "NASDAQ issued a delisting notice for failure to file 10-K on time. "
                "CFO resigned. Stock fell 33% in after-hours. Short interest was already 15% of float. "
                "Company denies all allegations and claims revenue is real."
            ),
            entities=["SMCI", "Hindenburg Research", "EY"],
            event_type="accounting_scandal",
            metadata={"ticker": "SMCI", "filing_date": "2024-10-31"},
        ),
        n_agents=200,
        n_rounds=10,
        archetype_config=None,
        expected_dynamic="cascade",
        why=(
            "Phase 1 (R1-3): InstitutionalAnalysts (high influence=0.90) initially split between "
            "'wait for facts' and 'sell the uncertainty'. MomentumTraders (recency=0.90) chase the "
            "price drop hard. Phase 2 (R4+): as more negative signals land, RetailFOMO (herding=0.70) "
            "amplifies the bearish cascade. ShortSeller resistance_override activates when consensus "
            "exceeds 0.6 — they become MORE stubborn in their bearish view, preventing recovery. "
            "ValueInvestors (contrarian=0.70, herding=-0.15) go against the crowd: they see the "
            "revenue as real and wait for the dust to settle. This creates a tail of bulls inside "
            "a strong bearish herd — a realistic pattern for fraud allegations."
        ),
        archetype_drivers=(
            "MomentumTrader (cascade amplifier) + ShortSeller (resistance lock-in) "
            "vs ValueInvestor (anti-herd tail)"
        ),
    ),

    Scenario(
        id="fin-2",
        title="GME-style short squeeze: retail vs institutional",
        domain="finance",
        use_enricher=False,
        seed_kwargs=dict(
            domain_id="finance",
            raw_input={"ticker": "GME"},
            summary=(
                "GameStop (GME) short interest has reached 140% of float — the highest recorded level "
                "for a US-listed stock. WallStreetBets community (8M members) is coordinating a "
                "short squeeze via call option purchases. Delta hedging by market makers is creating "
                "a reflexive gamma squeeze. Stock up 400% in 5 days. "
                "Robinhood has restricted buy orders citing clearinghouse margin requirements. "
                "Citadel and Melvin Capital (major short holders) reportedly in liquidity distress. "
                "Fundamental valuation: brick-and-mortar gaming retail, declining revenue, no clear "
                "path to digital pivot. Ryan Cohen joined board with 13% stake."
            ),
            entities=["GME", "WallStreetBets", "Citadel", "Melvin Capital", "Ryan Cohen"],
            event_type="short_squeeze",
            metadata={"ticker": "GME", "filing_date": "2021-01-27"},
        ),
        n_agents=300,
        n_rounds=12,
        archetype_config={
            "RetailFOMO": 0.45,           # overweight retail (the actual user base)
            "ShortSeller": 0.12,          # overweight shorts (the other protagonist)
            "MomentumTrader": 0.20,
            "InstitutionalAnalyst": 0.08,
            "ValueInvestor": 0.10,
            "PassiveLurker": 0.05,
        },
        expected_dynamic="bifurcation",
        why=(
            "The most interesting bifurcation scenario because of the ShortSeller resistance_override: "
            "when RetailFOMO social signal exceeds 0.6 bullish, ShortSellers' effective_resistance "
            "multiplies by 1.3, making them MORE stubborn — they dig in, not capitulate. "
            "Meanwhile RetailFOMO (herding=0.70) and MomentumTrader (herding=0.55) feed each other "
            "into a bullish herd. Result: two stable poles that resist convergence. "
            "ValueInvestors (contrarian=0.70) also go bearish on fundamentals, strengthening the "
            "bearish camp. Watch for the herding index to go negative as the two camps diverge."
        ),
        archetype_drivers=(
            "RetailFOMO herd (herding=0.70) vs ShortSeller resistance_override (resistance×1.3 "
            "when opposing signal > 0.6) — the strongest bifurcation driver in the system"
        ),
    ),

    Scenario(
        id="fin-3",
        title="Fed surprise: 50bp cut into strong jobs data",
        domain="finance",
        use_enricher=False,
        seed_kwargs=dict(
            domain_id="finance",
            raw_input={"ticker": "SPY"},
            summary=(
                "Federal Reserve cut rates by 50bp, double the 25bp expected by 92% of market participants. "
                "Fed Chair statement: 'We are recalibrating policy in light of the balance of risks.' "
                "Same week: non-farm payrolls +256K, unemployment 3.9%, core PCE 3.2% (above 2% target). "
                "Bond market pricing: 10Y yield up 12bp on the day (bonds selling off despite cut). "
                "Yield curve steepening sharply. Dollar weakening. Gold +2.1%. "
                "Historical base rate: Fed has cut 50bp outside of recession only twice (1998, 2001). "
                "Markets initially up 1.2%, then reversed -0.8% on growth concern interpretation."
            ),
            entities=["Federal Reserve", "SPY", "Treasury"],
            event_type="macro_policy",
            metadata={"ticker": "SPY", "filing_date": "2024-09-18"},
        ),
        n_agents=250,
        n_rounds=10,
        archetype_config={
            "MacroTourist": 0.25,         # overweight for macro event
            "InstitutionalAnalyst": 0.15,
            "ValueInvestor": 0.15,
            "MomentumTrader": 0.20,
            "RetailFOMO": 0.15,
            "ShortSeller": 0.05,
            "PassiveLurker": 0.05,
        },
        expected_dynamic="uncertain",
        why=(
            "The most genuinely ambiguous scenario. The same event reads as: "
            "(a) 'The Fed panicked — recession is coming' (bearish, ValueInvestor/MacroTourist) "
            "(b) 'Cheap money is back — buy everything' (bullish, RetailFOMO/MomentumTrader) "
            "(c) 'Stagflation risk — sell bonds, buy real assets' (neutral-to-bullish, InstitutionalAnalyst). "
            "MacroTourists (overweighted here) have moderate parameters and will produce the most "
            "interesting split. Watch for: low settled fraction, moderate herding, multiple "
            "cascade events as interpretations flip. ADS should be very high (many angles surfacing)."
        ),
        archetype_drivers=(
            "MacroTourist (balanced parameters) vs InstitutionalAnalyst (high influence, split signal) "
            "— no archetype dominates, producing genuine multi-polar uncertainty"
        ),
    ),

    Scenario(
        id="fin-4",
        title="SVB collapse: uninsured depositor panic",
        domain="finance",
        use_enricher=False,
        seed_kwargs=dict(
            domain_id="finance",
            raw_input={"ticker": "SIVB"},
            summary=(
                "Silicon Valley Bank (SIVB) announced a $1.8B after-tax loss on sale of its "
                "available-for-sale bond portfolio (forced by deposit outflows) and a $2.25B "
                "equity raise to shore up capital. 94% of deposits are uninsured (>$250K FDIC limit). "
                "Deposit base: 37,000 small businesses, most of which cannot survive more than 2 weeks "
                "without access to funds. Peter Thiel's Founders Fund withdrew all deposits. "
                "Sequoia, Coatue, Union Square Ventures sent portfolio company advisory notices. "
                "Bank has $209B in assets but $15B in unrealized losses on HTM securities. "
                "FDIC intervention announced. Trading halted."
            ),
            entities=["SIVB", "FDIC", "Sequoia", "Founders Fund"],
            event_type="bank_failure",
            metadata={"ticker": "SIVB", "filing_date": "2023-03-10"},
        ),
        n_agents=200,
        n_rounds=8,
        archetype_config={
            "InstitutionalAnalyst": 0.20,  # heavy — they move markets here
            "MomentumTrader": 0.25,
            "RetailFOMO": 0.25,
            "ShortSeller": 0.10,
            "ValueInvestor": 0.10,
            "PassiveLurker": 0.10,
        },
        expected_dynamic="cascade",
        why=(
            "Classic multi-wave cascade: information arrives in stages. "
            "R1-2: InstitutionalAnalysts cautiously negative (loss announcement is bad, but manageable). "
            "R3-4: Cascade 1 — VC advisory emails leak, MomentumTraders and RetailFOMO flood bearish. "
            "ShortSellers (already positioned short SVB) become more confident and stubborn. "
            "ValueInvestors briefly consider buying the dip (high contrarian tendency) but the "
            "speed of information flow overwhelms their resistance. "
            "Expected: two distinct cascade events with herding_index oscillating, "
            "then rapid convergence to strong bearish as the bank failure is confirmed."
        ),
        archetype_drivers=(
            "InstitutionalAnalyst (high influence) sets the initial frame; "
            "MomentumTrader + RetailFOMO amplify the cascade; "
            "ShortSeller resistance_override prevents bounce"
        ),
    ),

    # ── Coding scenarios ──────────────────────────────────────────────────────

    Scenario(
        id="code-1",
        title="Security CVE fix: SQL injection in Django ORM",
        domain="coding",
        use_enricher=True,   # uses real GitHub enricher
        seed_kwargs=dict(
            raw_input={"pr_url": "https://github.com/django/django/pull/17752"}
        ),
        n_agents=100,
        n_rounds=6,
        archetype_config=None,
        expected_dynamic="herd",
        why=(
            "SecurityReviewer (influence=0.75, resistance=0.80) dominates early: a CVE fix is "
            "an unambiguous approve signal. DomainExpertMaintainer (influence=0.90, resistance=0.85) "
            "will do the authoritative technical review and stamp it. "
            "JuniorContributors (40% of pop, herding=0.65) rapidly follow the senior signal. "
            "StyleMaintainability reviewers may want minor cleanup but won't block. "
            "Expected: fast, clean herd toward approve. Low cascade events (signal is clear). "
            "High settled fraction early — once a CVE is approved, opinions don't oscillate."
        ),
        archetype_drivers=(
            "SecurityReviewer (high influence, unambiguous approve) + "
            "DomainExpertMaintainer (highest influence, stamps it) → "
            "JuniorContributor herd follows"
        ),
    ),

    Scenario(
        id="code-2",
        title="Breaking API change: remove deprecated auth middleware",
        domain="coding",
        use_enricher=True,
        seed_kwargs=dict(
            # A PR that removes a long-deprecated but still widely-used API
            # Substitute any large breaking-change PR URL here
            raw_input={"pr_url": "https://github.com/psf/requests/pull/6730"}
        ),
        n_agents=120,
        n_rounds=8,
        archetype_config={
            "SecurityReviewer": 0.12,       # approve: removes attack surface
            "PerformanceReviewer": 0.10,    # neutral-positive: less code = faster
            "StyleMaintainability": 0.30,   # BLOCK: no migration guide, breaks semver
            "DomainExpertMaintainer": 0.15, # split: technically right, politically painful
            "JuniorContributor": 0.33,      # follows whoever speaks loudest
        },
        expected_dynamic="bifurcation",
        why=(
            "Classic open-source governance split. SecurityReviewer and PerformanceReviewer "
            "approve (removing deprecated code is good hygiene). StyleMaintainability "
            "(overweighted here, high herding=0.40) blocks: no migration guide, no deprecation "
            "warning period, potential SemVer violation. DomainExpertMaintainer (highest "
            "influence=0.90) is genuinely split — they know both arguments. "
            "JuniorContributors form the swing vote and will herd toward whichever archetype "
            "makes the loudest early argument. Watch for: herding index flat or negative, "
            "cascade when DomainExpertMaintainer finally takes a stance."
        ),
        archetype_drivers=(
            "StyleMaintainability (blocks, high proportion) vs SecurityReviewer (approves) — "
            "DomainExpertMaintainer's final stance determines which camp JuniorContributors join"
        ),
    ),

    Scenario(
        id="code-3",
        title="AI-generated mass refactor: correct but inhuman",
        domain="coding",
        use_enricher=False,
        seed_kwargs=dict(
            domain_id="coding",
            raw_input={"pr_url": "ai-generated"},
            summary=(
                "PR adds 3,400 lines: full refactor of the authentication module using AI-assisted "
                "generation. Code is syntactically correct and all 847 tests pass (CI green). "
                "However: zero inline comments, variable names are semantically valid but unusual "
                "('auth_state_transformer_v2', 'credential_pipeline_executor'), no docstrings, "
                "and the git history shows all 3,400 lines committed in a single 2-minute session. "
                "The author's GitHub profile shows 3 commits total, all in the last week. "
                "No PR description beyond 'refactor auth module for better performance'. "
                "Benchmark shows 8% latency improvement in auth paths."
            ),
            entities=["auth module"],
            event_type="refactor",
            metadata={
                "diff_size_tier": "xl",
                "languages_touched": ["Python"],
                "is_test_included": True,
                "author_pr_history": 0,
                "ci_pass_rate": 1.0,
            },
        ),
        n_agents=120,
        n_rounds=8,
        archetype_config=None,
        expected_dynamic="uncertain",
        why=(
            "This scenario has no clear correct answer, which is what makes it interesting. "
            "SecurityReviewer: deeply suspicious (AI code may have subtle auth vulnerabilities, "
            "unreadable code is an attack surface). Contrarian tendency=0.60 means they'll "
            "resist the 'CI passes = it's fine' herd. "
            "PerformanceReviewer: positively biased (8% improvement is real). "
            "StyleMaintainability: strong block (zero comments, unusual naming, maintainability disaster). "
            "DomainExpertMaintainer: likely block (can't review what you can't read; "
            "domain expertise requires understandable code). "
            "JuniorContributor: conflicted — CI green signals approve, but everyone else is cautious. "
            "Expected: moderate herding toward block, multiple cascade events as different "
            "archetypes weigh in, high ADS (many argument angles), low settled fraction."
        ),
        archetype_drivers=(
            "SecurityReviewer and DomainExpertMaintainer (both high resistance) likely block. "
            "PerformanceReviewer approves. JuniorContributor is the swing: they'll herd toward "
            "whichever camp makes the most recent argument (recency_bias=0.80)."
        ),
    ),

]


# ── Runner ────────────────────────────────────────────────────────────────────

def _bar(value: float, width: int = 28) -> str:
    mid = width // 2
    norm = (value + 1.0) / 2.0
    pos = max(0, min(width - 1, int(norm * width)))
    bar = ["-"] * width
    bar[mid] = "|"
    if pos < mid:
        for i in range(pos, mid):
            bar[i] = _RED + "█" + _RESET
    elif pos > mid:
        for i in range(mid + 1, pos + 1):
            bar[i] = _GREEN + "█" + _RESET
    return "[" + "".join(bar) + "]"


def _hbar(h: float, width: int = 16) -> str:
    pct = max(-200, min(100, h * 100))
    if pct < 0:
        return _RED + f"◀ {pct:.0f}%" + _RESET
    filled = min(int(h * width), width)
    col = _YELLOW if pct < 40 else _GREEN
    return col + "▓" * filled + _DIM + "░" * (width - filled) + _RESET + f" {pct:.0f}%"


def _print_round(event: RoundEvent) -> None:
    sm = event.social_metrics
    m, sd = event.mean_opinion, event.stddev_opinion
    cascade = f"  {_YELLOW}⚡{sm.cascade_trigger_archetype}{_RESET}" if sm and sm.cascade_detected else ""
    settled = f"  settled={sm.settled_fraction:.0%}" if sm and sm.settled_fraction > 0 else ""
    tags = f"  +[{', '.join(sm.new_argument_tags)}]" if sm and sm.new_argument_tags else ""
    h_str = _hbar(sm.herding_index) if sm else "---"
    ads = f"  ADS={sm.argument_diversity_score:.0%}" if sm else ""
    print(f"  R{event.round_number:02d}  {_bar(m)}  {m:+.3f} ±{sd:.3f}"
          f"  H={h_str}{ads}{tags}{cascade}{settled}")
    if event.sample_posts:
        p = event.sample_posts[0]
        col = _GREEN if p.stance in ("bullish", "approve") else _RED
        print(f"        {_DIM}{p.archetype:<22}{_RESET}{col}{p.stance:<8}{_RESET}"
              f" [{p.argument_tag}]  \"{p.blurb[:80]}\"")


def _print_summary(result: SimulationResult, scenario: Scenario) -> None:
    h_curve = result.herding_curve
    cascades = [e for e in result.round_events if e.social_metrics and e.social_metrics.cascade_detected]
    final_settled = result.round_events[-1].social_metrics.settled_fraction if result.round_events[-1].social_metrics else 0
    print(f"\n  {_BOLD}Summary{_RESET}")
    print(f"  Trajectory    : {' → '.join(f'{v:+.2f}' for v in result.trajectory)}")
    print(f"  Peak herding  : {max(h_curve):.0%}   Min: {min(h_curve):.0%}")
    print(f"  ADS final     : {len(result.argument_timeline)}/{len(result.argument_timeline) + max(0, 8 - len(result.argument_timeline))} tags")
    print(f"  Cascades      : {len(cascades)}  rounds={[e.round_number for e in cascades]}")
    print(f"  Final settled : {final_settled:.0%}")
    print(f"  Argument arc  : {' → '.join(t for t, _ in sorted(result.argument_timeline.items(), key=lambda x: x[1]))}")


def run_scenario(scenario: Scenario) -> None:
    print(f"\n{_BOLD}{'═'*64}{_RESET}")
    print(f"{_BOLD}  {scenario.id}: {scenario.title}{_RESET}")
    print(f"  Domain: {scenario.domain}  |  Expected: {_CYAN}{scenario.expected_dynamic}{_RESET}")
    print(f"  Drivers: {_DIM}{scenario.archetype_drivers}{_RESET}")
    print(f"{_BOLD}{'═'*64}{_RESET}\n")

    if scenario.domain == "finance":
        from lightningfish_finance.config import FinanceDomainAdapter
        adapter = FinanceDomainAdapter()
    else:
        from lightningfish_coding.config import CodingDomainAdapter
        adapter = CodingDomainAdapter()

    if scenario.use_enricher:
        print("  Enriching seed (live API call)...")
        seed = adapter.enrich_seed(scenario.seed_kwargs["raw_input"])
    else:
        kw = {k: v for k, v in scenario.seed_kwargs.items()}
        seed = EnrichedSeed(**kw)

    print(f"  Seed: {seed.summary[:120]}...\n" if len(seed.summary) > 120 else f"  Seed: {seed.summary}\n")

    agents = adapter.build_personas(scenario.n_agents, scenario.archetype_config)
    archetype_counts = {}
    for a in agents:
        archetype_counts[a.archetype] = archetype_counts.get(a.archetype, 0) + 1
    print(f"  Agents ({len(agents)}): " +
          ", ".join(f"{k}={v}" for k, v in sorted(archetype_counts.items(), key=lambda x: -x[1])))
    print()

    model = os.environ.get("LIGHTNINGFISH_MODEL", "claude-haiku-4-5-20251001")
    engine = SimulationEngine(adapter, model=model)
    result = engine.run(seed, agents, n_rounds=scenario.n_rounds)

    for event in result.round_events:
        _print_round(event)

    _print_summary(result, scenario)


def list_scenarios() -> None:
    print(f"\n{_BOLD}Available scenarios{_RESET}\n")
    for s in _SCENARIOS:
        dyn_col = {
            "herd": _GREEN, "cascade": _YELLOW,
            "bifurcation": _RED, "uncertain": _CYAN,
        }.get(s.expected_dynamic, "")
        print(f"  {_BOLD}{s.id:<10}{_RESET} {s.title}")
        print(f"            domain={s.domain}  expected={dyn_col}{s.expected_dynamic}{_RESET}")
        print(f"            {_DIM}{s.why[:120]}...{_RESET}\n")
    print("Usage:  python -m tests.integration.real_scenarios <id>\n"
          "        LIGHTNINGFISH_MODEL=claude-haiku-4-5-20251001  (default, cheapest)\n"
          "        LIGHTNINGFISH_MODEL=claude-sonnet-4-6           (better reasoning)\n")


def main() -> None:
    if len(sys.argv) < 2:
        list_scenarios()
        return

    sid = sys.argv[1]
    scenario = next((s for s in _SCENARIOS if s.id == sid), None)
    if scenario is None:
        print(f"Unknown scenario '{sid}'. Run without arguments to list all.")
        sys.exit(1)

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Error: ANTHROPIC_API_KEY not set.")
        sys.exit(1)

    run_scenario(scenario)


if __name__ == "__main__":
    main()
