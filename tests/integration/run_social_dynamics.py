"""
Integration script: exercises the full social simulation engine with scripted
LLM responses to surface interesting herd/cascade/bifurcation dynamics.

Run:
    python -m tests.integration.run_social_dynamics
"""
from __future__ import annotations

import io
import sys
import uuid

# Force UTF-8 output on Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from dataclasses import dataclass

from lightningfish_core.adapter import DomainAdapter
from lightningfish_core.engine import SimulationEngine
from lightningfish_core.models import (
    AgentPersona,
    BacktestResult,
    EnrichedSeed,
    RoundEvent,
    SimulationResult,
)
from lightningfish_core.social import SocialPost

# ── ANSI colours ──────────────────────────────────────────────────────────────
_RESET  = "\033[0m"
_BOLD   = "\033[1m"
_DIM    = "\033[2m"
_GREEN  = "\033[32m"
_RED    = "\033[31m"
_YELLOW = "\033[33m"
_CYAN   = "\033[36m"
_BLUE   = "\033[34m"
_MAGENTA = "\033[35m"


def _bar(value: float, lo: float = -1.0, hi: float = 1.0, width: int = 30) -> str:
    """Render a bipolar bar. Centre = 0, left = negative, right = positive."""
    mid = width // 2
    norm = (value - lo) / (hi - lo)
    pos = int(norm * width)
    pos = max(0, min(width - 1, pos))
    bar = ["-"] * width
    bar[mid] = "|"
    if pos < mid:
        for i in range(pos, mid):
            bar[i] = _RED + "█" + _RESET
    elif pos > mid:
        for i in range(mid + 1, pos + 1):
            bar[i] = _GREEN + "█" + _RESET
    return "[" + "".join(bar) + "]"


def _herd_bar(h: float, width: int = 20) -> str:
    """0–100% bar for herding index, red if negative."""
    pct = h * 100
    if pct < 0:
        return _RED + f"◀ {pct:+.0f}%" + _RESET
    filled = min(int(h * width), width)
    colour = _YELLOW if pct < 40 else _GREEN
    return colour + "▓" * filled + _DIM + "░" * (width - filled) + _RESET + f" {pct:.0f}%"


# ── Taxonomy shared across scenarios ──────────────────────────────────────────
TAXONOMY = ["valuation", "momentum", "sentiment", "technical",
            "macro", "catalyst", "quality", "liquidity"]

# Argument tags introduced progressively: simulates "argument space filling up"
ROUND_TAGS = {
    1: "valuation",
    2: "momentum",
    3: "sentiment",
    4: "technical",
    5: "macro",
    6: "catalyst",
    7: "quality",
    8: "liquidity",
}


# ── Scripted LLM provider ─────────────────────────────────────────────────────
@dataclass
class _ScriptedProvider:
    """
    Deterministic fake LLM. Returns per-round opinion scripts.
    t1_script: list of (opinion, stance, tag, blurb) per round (index = round-1)
    t2_script: list of [opinion, ...] per round
    """
    t1_script: list[tuple[float, str, str, str]]   # one entry per round
    t2_script: list[list[float]]                    # one list per round
    _round: int = 0

    def generate_post(
        self, system: str, model: str,
        agent_id: str, archetype: str, round_number: int, opinion_before: float,
    ) -> tuple[SocialPost, float, float]:
        idx = min(round_number - 1, len(self.t1_script) - 1)
        opinion, stance, tag, blurb = self.t1_script[idx]
        post = SocialPost(
            agent_id=agent_id, archetype=archetype,
            round_number=round_number, stance=stance,
            argument_tag=tag, confidence=0.7 + 0.05 * idx,
            blurb=blurb, opinion_before=opinion_before, opinion_after=opinion,
        )
        return post, opinion, 0.0

    def batch_opinions_from_feed(
        self, systems: list[str], model: str,
    ) -> tuple[list[float], float]:
        # Use the current round index stored externally (pass via round counter)
        return list(self._t2_this_round[:len(systems)]), 0.0

    def set_round(self, round_number: int, n_t2: int) -> None:
        idx = min(round_number - 1, len(self.t2_script) - 1)
        raw = self.t2_script[idx]
        # Cycle the script list to fill n_t2 slots
        self._t2_this_round = [raw[i % len(raw)] for i in range(n_t2)]


class _InstrumentedEngine(SimulationEngine):
    """Injects set_round call before each T2 batch so the scripted provider tracks rounds."""

    def run_streaming(self, seed, agents, n_rounds):  # type: ignore[override]
        gen = super().run_streaming(seed, agents, n_rounds)
        return gen


# We monkeypatch batch_opinions_from_feed to inject round number
class _TrackingProvider:
    def __init__(self, scripted: _ScriptedProvider) -> None:
        self._s = scripted
        self._current_round = 1

    def generate_post(self, system, model, agent_id, archetype, round_number, opinion_before):
        self._current_round = round_number
        return self._s.generate_post(system, model, agent_id, archetype, round_number, opinion_before)

    def batch_opinions_from_feed(self, systems, model):
        self._s.set_round(self._current_round, len(systems))
        return self._s.batch_opinions_from_feed(systems, model)

    def get_opinion(self, system, user_msg, model):
        return 0.0, 0.0


# ── Stub domain adapter ───────────────────────────────────────────────────────
class _StubAdapter(DomainAdapter):
    domain_id = "finance"
    display_name = "Finance"
    opinion_labels = ("bearish", "bullish")

    def enrich_seed(self, r): return self._seed
    def build_personas(self, n, archetype_config=None): return []
    def agent_system_prompt(self, seed, persona): return "stub"
    def post_system_prompt(self, seed, persona, feed, viral): return "stub"
    def argument_taxonomy(self): return list(TAXONOMY)
    def get_ground_truth(self, seed): return None
    def score(self, result, truth): return BacktestResult(True, 0.0, {}, 0, 0.0)

    def __init__(self, seed: EnrichedSeed) -> None:
        self._seed = seed


# ── Agent factories ────────────────────────────────────────────────────────────
def _agents_spread(n: int, lo: float = -0.7, hi: float = 0.7,
                   archetypes: list[str] | None = None) -> list[AgentPersona]:
    """n agents uniformly spread from lo to hi."""
    archetypes = archetypes or ["Analyst", "Trader", "Quant", "RetailInvestor"]
    agents = []
    for i in range(n):
        frac = i / max(n - 1, 1)
        opinion = lo + frac * (hi - lo)
        agents.append(AgentPersona(
            unique_id=str(uuid.uuid4()),
            archetype=archetypes[i % len(archetypes)],
            opinion_resistance=0.4,
            recency_bias=0.6,
            contrarian_tendency=0.05,
            influence_weight=0.85 if i < max(1, int(n * 0.10)) else 0.3,
            proportion=1.0 / n,
            herding_coefficient=0.35,
            current_opinion=round(opinion, 3),
        ))
    return agents


def _agents_polarised(n: int) -> list[AgentPersona]:
    """Half Bulls at +0.7, half Bears at -0.7 — sets up bifurcation."""
    agents = []
    for i in range(n):
        archetype = "Bull" if i < n // 2 else "Bear"
        opinion = 0.7 if i < n // 2 else -0.7
        agents.append(AgentPersona(
            unique_id=str(uuid.uuid4()),
            archetype=archetype,
            opinion_resistance=0.7,      # high: hard to change mind
            recency_bias=0.3,
            contrarian_tendency=0.0,
            influence_weight=0.85 if i % (n // 2) < 2 else 0.3,
            proportion=1.0 / n,
            herding_coefficient=0.5,     # strong pull toward own cluster
            current_opinion=opinion,
        ))
    return agents


# ── Rich printer ──────────────────────────────────────────────────────────────
def _print_round(event: RoundEvent, pole_lo: str = "Bearish", pole_hi: str = "Bullish") -> None:
    sm = event.social_metrics
    mean = event.mean_opinion
    std  = event.stddev_opinion

    print(f"  R{event.round_number:02d}  opinion {mean:+.3f}  σ={std:.3f}  "
          f"{_bar(mean)}  "
          f"T1={event.tier1_calls}", end="")

    if sm:
        h = sm.herding_index
        cascade_flag = f"  {_YELLOW}⚡CASCADE({sm.cascade_trigger_archetype}){_RESET}" if sm.cascade_detected else ""
        settled_flag = f"  settled={sm.settled_fraction:.0%}" if sm.settled_fraction > 0 else ""
        new_tags = f"  +[{', '.join(sm.new_argument_tags)}]" if sm.new_argument_tags else ""
        print(f"  H={_herd_bar(h, 12)}"
              f"  ADS={sm.argument_diversity_score:.0%}"
              f"{new_tags}{cascade_flag}{settled_flag}")
    else:
        print()

    if event.sample_posts:
        for p in event.sample_posts[:3]:
            colour = _GREEN if p.stance in ("bullish", "approve") else _RED
            print(f"        {_DIM}{p.archetype:<20}{_RESET}"
                  f"{colour}{p.stance:<8}{_RESET}  [{p.argument_tag}]  \"{p.blurb}\"")


def _print_summary(result: SimulationResult, title: str) -> None:
    print(f"\n  {_BOLD}── Summary ──────────────────────────────────{_RESET}")
    print(f"  Final mean opinion : {result.trajectory[-1]:+.3f}")
    traj_delta = result.trajectory[-1] - result.trajectory[0]
    print(f"  Trajectory shift   : {traj_delta:+.3f}  "
          f"({'converging' if abs(traj_delta) > 0.05 else 'stable'})")
    print(f"  Peak herding index : {max(result.herding_curve):.2%}")
    print(f"  Min  herding index : {min(result.herding_curve):.2%}"
          f"  {'← bifurcation detected' if min(result.herding_curve) < 0 else ''}")
    print(f"  Unique arg. tags   : {len(result.argument_timeline)}/{len(TAXONOMY)}"
          f"  ADS={len(result.argument_timeline)/len(TAXONOMY):.0%}")
    print("  Argument timeline  :")
    for tag, rnd in sorted(result.argument_timeline.items(), key=lambda x: x[1]):
        print(f"    R{rnd:02d}  {tag}")
    cascades = [e for e in result.round_events if e.social_metrics and e.social_metrics.cascade_detected]
    if cascades:
        print(f"  Cascades           : {len(cascades)} event(s) — "
              f"rounds {[e.round_number for e in cascades]}")
    herding_curve_str = "  ".join(f"{h:+.2f}" for h in result.herding_curve)
    print(f"  Herding curve      : {herding_curve_str}")


# ── Scenarios ─────────────────────────────────────────────────────────────────

def scenario_herd_formation() -> SimulationResult:
    """
    Scenario A: "Earnings Surprise → Herd Formation"
    --------------------------------------------------
    50 agents start spread across [-0.7, +0.7].
    T1 agents consistently return bullish opinions that ramp from 0.4 → 0.85.
    T2 batch opinions are pulled toward the growing consensus.
    T3 herding math amplifies the pull.

    Expected behaviour:
    - herding_index rises monotonically (converging opinions)
    - settled_fraction rises as agents lock in
    - argument tags progress from 'valuation' → 'momentum' → 'sentiment' (narrative shifts)
    - no cascade (gradual, not sudden)
    """
    seed = EnrichedSeed("finance", {}, "AAPL Q4 beat: revenue +18% YoY, EPS $1.64 vs $1.60 est.",
                        ["AAPL"], "earnings", {"ticker": "AAPL"})

    # T1: ramp from moderate bullish → strong bullish
    t1_script = [
        (0.40, "bullish", "valuation",  "FCF yield at 5.8% signals undervaluation relative to growth peers."),
        (0.52, "bullish", "momentum",   "Price action confirms breakout above 200-DMA on high volume."),
        (0.61, "bullish", "sentiment",  "Retail flow surging; Reddit mentions up 3x post earnings."),
        (0.68, "bullish", "technical",  "RSI reset from overbought; retest of breakout looks constructive."),
        (0.73, "bullish", "catalyst",   "Services revenue acceleration is the real upside surprise."),
        (0.78, "bullish", "macro",      "Rate cut cycle supports multiple expansion for quality growth."),
        (0.82, "bullish", "quality",    "Operating leverage improving; margin expansion sustainable."),
        (0.85, "bullish", "liquidity",  "Buyback programme absorbs 3% of float per year — structurally supportive."),
    ]

    # T2: opinions pulled toward consensus, accelerating each round
    t2_script = [
        [0.20, 0.25, 0.30, 0.15],
        [0.30, 0.35, 0.40, 0.28],
        [0.42, 0.45, 0.50, 0.38],
        [0.52, 0.55, 0.58, 0.48],
        [0.60, 0.62, 0.65, 0.55],
        [0.67, 0.68, 0.70, 0.62],
        [0.72, 0.73, 0.75, 0.68],
        [0.78, 0.79, 0.80, 0.74],
    ]

    scripted = _ScriptedProvider(t1_script=t1_script, t2_script=t2_script)
    provider = _TrackingProvider(scripted)
    agents = _agents_spread(50)
    adapter = _StubAdapter(seed)
    engine = SimulationEngine(adapter, model="test")
    engine.provider = provider  # type: ignore[assignment]

    return engine.run(seed, agents, n_rounds=8)


def scenario_cascade_reversal() -> SimulationResult:
    """
    Scenario B: "Analyst Downgrade Cascade"
    -----------------------------------------
    30 agents start mildly bullish (0.1–0.4).
    First 3 rounds: stable, moderate consensus forms (~0.3).
    Round 4: top T1 Analysts return -0.55 (shock downgrade).
    Rounds 5–6: opinion partially recovers but remains negative.

    Expected behaviour:
    - cascade_detected=True in round 4 (|mean_4 - mean_3| > 0.15)
    - herding_index dips sharply when the reversal hits
    - Analyst archetype named as cascade_trigger
    - argument tags shift from 'valuation'/'momentum' to 'technical'/'risk'
    """
    seed = EnrichedSeed("finance", {},
                        "NVDA: analyst cluster downgrades citing margin compression and China export curbs.",
                        ["NVDA"], "analyst_action", {"ticker": "NVDA"})

    t1_script = [
        (0.35, "bullish", "valuation",   "Forward P/E at 28x leaves room for further re-rating."),
        (0.38, "bullish", "momentum",    "Data centre pipeline commentary was incrementally positive."),
        (0.32, "bullish", "sentiment",   "Buy-side still constructive; short interest near 12-month low."),
        (-0.55, "bearish", "technical",  "Triple downgrade by Goldman / JPM / Barclays — margin model broken."),
        (-0.42, "bearish", "macro",      "China export restriction removes $4B addressable market immediately."),
        (-0.28, "bearish", "catalyst",   "Next catalyst is Q1 guide in 8 weeks; risk/reward skewed negative."),
    ]

    t2_script = [
        [0.20, 0.25, 0.18],
        [0.28, 0.30, 0.22],
        [0.25, 0.28, 0.20],
        [-0.30, -0.25, -0.20, -0.35],  # sharp reversal following T1 downgrade
        [-0.22, -0.18, -0.25, -0.15],
        [-0.12, -0.10, -0.18, -0.08],
    ]

    scripted = _ScriptedProvider(t1_script=t1_script, t2_script=t2_script)
    provider = _TrackingProvider(scripted)
    agents = _agents_spread(30, lo=0.1, hi=0.45)
    adapter = _StubAdapter(seed)
    engine = SimulationEngine(adapter, model="test")
    engine.provider = provider  # type: ignore[assignment]

    return engine.run(seed, agents, n_rounds=6)


def scenario_tribal_bifurcation() -> SimulationResult:
    """
    Scenario C: "Bull vs Bear Tribal Lock-In"
    -------------------------------------------
    40 agents, half starting at +0.7 (Bulls), half at -0.7 (Bears).
    High opinion_resistance (0.7) — agents are stubborn.
    T1 Bulls → +0.8, T1 Bears → -0.8. No middle ground.

    Expected behaviour:
    - herding_index goes NEGATIVE — population is MORE polarised than round 1
    - High stddev throughout
    - Argument tags split by archetype: Bulls use 'valuation'/'quality',
      Bears use 'macro'/'liquidity' — but the mock alternates between them
    - settled_fraction rises but at opposite poles
    """
    seed = EnrichedSeed("finance", {},
                        "Fed signals higher-for-longer; market divided on recession probability.",
                        ["SPX"], "macro_event", {"ticker": "SPX"})

    # T1 alternates Bull/Bear every round based on which archetype gets T1 slot
    # We return mixed signals, but since agents are high-resistance, T3 herding
    # pulls them deeper into their own clusters
    t1_script = [
        (0.78,  "bullish", "valuation",   "Soft landing remains base case; earnings resilience intact."),
        (-0.75, "bearish", "macro",       "Real yields at 2.1% — historical recession signal activated."),
        (0.72,  "bullish", "quality",     "Quality factor outperforms in late-cycle; rotation supportive."),
        (-0.70, "bearish", "liquidity",   "M2 contraction of 4.5% YoY historically precedes risk-off."),
        (0.68,  "bullish", "catalyst",    "Earnings season 73% beat rate defies recessionary narrative."),
        (-0.65, "bearish", "technical",   "200-week MA breach — secular bull market structure broken."),
        (0.65,  "bullish", "momentum",    "Breadth improving; equal-weight S&P outperforming cap-weight."),
        (-0.60, "bearish", "sentiment",   "AAII survey at 62% bearish — capitulation imminent but painful."),
    ]

    t2_script = [
        [0.65, 0.60, -0.60, -0.65],
        [0.70, 0.65, -0.65, -0.70],
        [0.72, 0.68, -0.68, -0.72],
        [0.74, 0.70, -0.70, -0.74],
        [0.75, 0.71, -0.71, -0.75],
        [0.76, 0.72, -0.72, -0.76],
        [0.77, 0.73, -0.73, -0.77],
        [0.78, 0.74, -0.74, -0.78],
    ]

    scripted = _ScriptedProvider(t1_script=t1_script, t2_script=t2_script)
    provider = _TrackingProvider(scripted)
    agents = _agents_polarised(40)
    adapter = _StubAdapter(seed)
    engine = SimulationEngine(adapter, model="test")
    engine.provider = provider  # type: ignore[assignment]

    return engine.run(seed, agents, n_rounds=8)


# ── Semantic analysis ─────────────────────────────────────────────────────────

def semantic_analysis(results: dict[str, SimulationResult]) -> None:
    print(f"\n{_BOLD}{'═'*60}{_RESET}")
    print(f"{_BOLD}  CROSS-SCENARIO SEMANTIC ANALYSIS{_RESET}")
    print(f"{_BOLD}{'═'*60}{_RESET}\n")

    # 1. Herding comparison
    print(f"  {_BOLD}Herding index trajectory (per scenario){_RESET}")
    for name, result in results.items():
        curve = result.herding_curve
        peak = max(curve)
        trough = min(curve)
        direction = "↑ converging" if curve[-1] > curve[0] else "↓ diverging"
        print(f"    {name:<28}  peak={peak:+.2%}  trough={trough:+.2%}  {direction}")

    # 2. Cascade detection
    print(f"\n  {_BOLD}Cascade events{_RESET}")
    for name, result in results.items():
        events = [e for e in result.round_events
                  if e.social_metrics and e.social_metrics.cascade_detected]
        if events:
            for e in events:
                sm = e.social_metrics
                delta = abs(e.mean_opinion - (result.round_events[e.round_number - 2].mean_opinion
                            if e.round_number > 1 else e.mean_opinion))
                print(f"    {name:<28}  R{e.round_number:02d}  Δmean={delta:+.3f}"
                      f"  trigger={sm.cascade_trigger_archetype}")
        else:
            print(f"    {name:<28}  no cascade")

    # 3. Argument diversity progression
    print(f"\n  {_BOLD}Argument diversity (ADS) by round{_RESET}")
    header = "    scenario                      " + "  ".join(f"R{i+1}" for i in range(8))
    print(header)
    for name, result in results.items():
        row_vals = []
        for event in result.round_events:
            if event.social_metrics:
                ads = event.social_metrics.argument_diversity_score
                row_vals.append(f"{ads:.0%}")
            else:
                row_vals.append(" -- ")
        print(f"    {name:<28}  {'  '.join(row_vals)}")

    # 4. Opinion convergence analysis
    print(f"\n  {_BOLD}Opinion distribution (mean ± σ) trajectory{_RESET}")
    for name, result in results.items():
        print(f"    {_BOLD}{name}{_RESET}")
        for event in result.round_events:
            m  = event.mean_opinion
            sd = event.stddev_opinion
            bar = _bar(m, width=24)
            pole = "Bullish" if m > 0.1 else ("Bearish" if m < -0.1 else "Neutral")
            print(f"      R{event.round_number:02d}  {bar}  {m:+.3f} ±{sd:.3f}  [{pole}]")

    # 5. Settled agent progression
    print(f"\n  {_BOLD}Settled agent fraction (opinion convergence by agent){_RESET}")
    for name, result in results.items():
        fracs = [f"{e.social_metrics.settled_fraction:.0%}" if e.social_metrics else "--"
                 for e in result.round_events]
        print(f"    {name:<28}  {' → '.join(fracs)}")

    # 6. Interpretation
    print(f"\n  {_BOLD}Interpretation{_RESET}")
    for name, result in results.items():
        final = result.trajectory[-1]
        peak_h = max(result.herding_curve)
        min_h  = min(result.herding_curve)
        n_cascades = sum(1 for e in result.round_events
                         if e.social_metrics and e.social_metrics.cascade_detected)
        ads_final = len(result.argument_timeline) / len(TAXONOMY)

        if min_h < 0:
            dyn = f"{_RED}bifurcation{_RESET} (peak H={peak_h:.0%}, trough H={min_h:.0%})"
        elif n_cascades > 0:
            dyn = f"{_YELLOW}cascade reversal{_RESET} ({n_cascades} event(s), final mean={final:+.3f})"
        elif peak_h > 0.5:
            dyn = f"{_GREEN}strong herd formation{_RESET} (H reached {peak_h:.0%}, consensus={final:+.3f})"
        else:
            dyn = f"weak herding (H={peak_h:.0%})"

        print(f"    {_BOLD}{name}{_RESET}: {dyn},  ADS={ads_final:.0%}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    scenarios = {
        "A: Herd Formation":        (scenario_herd_formation,    "Bearish", "Bullish"),
        "B: Cascade Reversal":      (scenario_cascade_reversal,  "Bearish", "Bullish"),
        "C: Tribal Bifurcation":    (scenario_tribal_bifurcation,"Bearish", "Bullish"),
    }

    all_results: dict[str, SimulationResult] = {}

    for title, (fn, pole_lo, pole_hi) in scenarios.items():
        print(f"\n{_BOLD}{'═'*60}{_RESET}")
        print(f"{_BOLD}  {title}{_RESET}")
        print(f"{_BOLD}{'═'*60}{_RESET}")

        result = fn()
        all_results[title] = result

        print(f"\n  {result.seed.summary}\n")
        for event in result.round_events:
            _print_round(event, pole_lo, pole_hi)

        _print_summary(result, title)

    semantic_analysis(all_results)

    # Sanity assertions
    print(f"\n{_BOLD}  Assertions{_RESET}")
    r_a = all_results["A: Herd Formation"]
    r_b = all_results["B: Cascade Reversal"]
    r_c = all_results["C: Tribal Bifurcation"]

    # Herding index is now a consensus level in [0, 1] (1 = everyone agrees).
    # A forms consensus (positive, rising trajectory; high final herding).
    assert r_a.trajectory[-1] > 0.1, f"A: expected bullish drift, got {r_a.trajectory[-1]:.3f}"
    assert r_a.trajectory[-1] > r_a.trajectory[0], "A: expected trajectory to rise under sustained signal"
    assert r_a.herding_curve[-1] > 0.7, f"A: expected strong consensus, got {r_a.herding_curve[-1]:.2%}"
    # B reverses direction after the shock (a cascade fires).
    assert any(e.social_metrics and e.social_metrics.cascade_detected for e in r_b.round_events), \
        "B: expected at least one cascade event"
    # C stays measurably more split than A the whole way: with real cross-group
    # contagion, conformists converge, so persistent divergence shows up as C
    # holding LOWER consensus than A rather than as a negative index.
    assert r_c.herding_curve[-1] < r_a.herding_curve[-1], \
        f"C: expected to stay more split than A ({r_c.herding_curve[-1]:.2%} vs {r_a.herding_curve[-1]:.2%})"
    assert min(r_c.herding_curve) < 0.5, f"C: expected high early dispersion, got {min(r_c.herding_curve):.2%}"
    assert len(r_a.argument_timeline) >= 4, "A: expected ≥4 argument tags surfaced"

    print(f"  {_GREEN}✓ All assertions passed{_RESET}\n")


if __name__ == "__main__":
    main()
