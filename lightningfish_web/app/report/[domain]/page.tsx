import { AgentChat } from "@/components/AgentChat";
import { OpinionChart } from "@/components/OpinionChart";
import { DistributionBar } from "@/components/DistributionBar";
import { ConsensusVerdict } from "@/components/ConsensusVerdict";
import Link from "next/link";
import type { SimulationResult } from "@/lib/types";
import { DOMAINS } from "@/lib/types";

async function getSimulation(id: string) {
  const pyUrl = process.env.PYTHON_SERVICE_URL ?? "http://localhost:8000";
  const res = await fetch(`${pyUrl}/simulate/${id}/result`, { cache: "no-store" });
  if (!res.ok) return null;
  return res.json() as Promise<{
    id: string;
    domain_id: string;
    status: string;
    result_json: SimulationResult;
    cost_usd: number;
    n_agents: number;
    n_rounds: number;
    seed_json: Record<string, unknown>;
  }>;
}

export default async function ReportPage({
  params,
}: {
  params: Promise<{ domain: string }>;
}) {
  const { domain: id } = await params;
  const sim = await getSimulation(id);

  if (!sim || sim.status !== "complete" || !sim.result_json) {
    return (
      <div className="max-w-xl mx-auto px-6 py-24 text-center">
        <p className="text-fg-muted mb-4">
          {sim?.status === "running"
            ? "Simulation still running — refresh in a moment."
            : "Report not found or simulation failed."}
        </p>
        <Link href="/" className="text-sm text-glow underline decoration-glow/30 underline-offset-2">
          Back to home
        </Link>
      </div>
    );
  }

  const result = sim.result_json;
  const domain = DOMAINS.find((d) => d.id === result.domain_id);
  const negativePole = domain?.negativePole ?? "Negative";
  const positivePole = domain?.positivePole ?? "Positive";
  const finalOpinion = result.trajectory[result.trajectory.length - 1] ?? 0;

  return (
    <div className="max-w-2xl mx-auto px-6 py-12">
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center gap-2 mb-2">
          <span className="eyebrow text-glow">
            {result.domain_id}
          </span>
          <span className="text-ink-600">/</span>
          <span className="text-xs text-fg-faint">{result.event_type?.replace(/_/g, " ")}</span>
        </div>
        <h1 className="font-display text-2xl text-fg mb-1">{result.seed_summary}</h1>
        <p className="text-xs text-fg-faint font-mono">
          {sim.n_agents} agents &middot; {sim.n_rounds} rounds &middot; ${sim.cost_usd.toFixed(4)}
        </p>
      </div>

      {/* Plain-English verdict — first thing a non-technical user reads */}
      <ConsensusVerdict
        finalOpinion={finalOpinion}
        trajectory={result.trajectory}
        distribution={result.final_distribution}
        negativePole={negativePole}
        positivePole={positivePole}
        nAgents={sim.n_agents}
        eventType={result.event_type ?? ""}
      />

      {/* Trajectory chart */}
      <div className="surface p-5 mb-5">
        <h2 className="eyebrow mb-4">
          Opinion over time
        </h2>
        <OpinionChart
          trajectory={result.trajectory}
          negativePole={negativePole}
          positivePole={positivePole}
        />
      </div>

      {/* Distribution */}
      <div className="surface p-5 mb-5">
        <h2 className="eyebrow mb-4">
          Final distribution
        </h2>
        <DistributionBar
          distribution={result.final_distribution}
          negativePole={negativePole}
          positivePole={positivePole}
        />
      </div>

      {/* Herding curve */}
      {result.herding_curve && result.herding_curve.length > 0 && (
        <div className="surface p-5 mb-5">
          <h2 className="eyebrow mb-1">
            Herding index by round
          </h2>
          <p className="text-xs text-fg-faint mb-4">
            Consensus level &middot; 100% = everyone agrees &middot; 0% = maximally split &middot; a falling bar means opinions are diverging
          </p>
          <div className="flex items-end gap-1 h-16">
            {result.herding_curve.map((h, i) => {
              const pct = Math.max(0, Math.min(100, h * 100));
              return (
                <div key={i} className="flex-1 flex flex-col items-center gap-1">
                  <div
                    className="w-full rounded-sm bg-spark shadow-[0_0_6px_rgba(255,179,67,0.4)]"
                    style={{ height: `${pct}%`, minHeight: h < 0 ? 0 : 2 }}
                    title={`R${i + 1}: ${(h * 100).toFixed(0)}%`}
                  />
                </div>
              );
            })}
          </div>
          <div className="flex justify-between text-xs text-fg-faint mt-1 font-mono">
            <span>R1</span>
            <span>R{result.herding_curve.length}</span>
          </div>
        </div>
      )}

      {/* Argument emergence timeline */}
      {result.argument_timeline && Object.keys(result.argument_timeline).length > 0 && (
        <div className="surface p-5 mb-5">
          <h2 className="eyebrow mb-1">
            Argument emergence
          </h2>
          <p className="text-xs text-fg-faint mb-3">
            First round each argument angle surfaced &middot;{" "}
            {Object.keys(result.argument_timeline).length}/8 taxonomy tags covered (
            {Math.round((Object.keys(result.argument_timeline).length / 8) * 100)}% ADS)
          </p>
          <div className="flex flex-wrap gap-2">
            {Object.entries(result.argument_timeline)
              .sort(([, a], [, b]) => a - b)
              .map(([tag, round]) => (
                <div
                  key={tag}
                  className="border border-ink-700 rounded-lg px-2.5 py-1.5 text-xs bg-ink-950/40"
                >
                  <span className="font-medium text-fg">{tag}</span>
                  <span className="text-fg-faint ml-1.5 font-mono">R{round}</span>
                </div>
              ))}
          </div>
        </div>
      )}

      {/* Agent interview */}
      <div className="mb-5">
        <h2 className="eyebrow mb-1">
          Ask an agent
        </h2>
        <p className="text-xs text-fg-faint mb-3">
          Pick a persona and ask how they reasoned about this event.
        </p>
        <AgentChat simulationId={id} domainId={result.domain_id} />
      </div>

      {/* Stats — collapsed to secondary detail */}
      <details className="mb-5">
        <summary className="text-xs text-fg-faint cursor-pointer hover:text-glow transition-colors">
          Simulation details
        </summary>
        <dl className="grid grid-cols-2 gap-3 text-sm mt-3 surface p-4">
          <div>
            <dt className="text-fg-faint text-xs">LLM calls</dt>
            <dd className="font-medium text-fg font-mono">{result.total_tier1_calls}</dd>
          </div>
          <div>
            <dt className="text-fg-faint text-xs">Cost (USD)</dt>
            <dd className="font-medium text-fg font-mono">${sim.cost_usd.toFixed(5)}</dd>
          </div>
          <div>
            <dt className="text-fg-faint text-xs">Rounds</dt>
            <dd className="font-medium text-fg font-mono">{result.trajectory.length}</dd>
          </div>
          <div>
            <dt className="text-fg-faint text-xs">Population</dt>
            <dd className="font-medium text-fg font-mono">{sim.n_agents}</dd>
          </div>
        </dl>
      </details>

      {/* Footer nav */}
      <div className="pt-4 border-t border-ink-700 flex items-center justify-between text-sm">
        <Link href="/history" className="text-fg-faint hover:text-glow transition-colors">
          &larr; History
        </Link>
        <Link href="/" className="text-fg-faint hover:text-glow transition-colors">
          New simulation
        </Link>
      </div>
    </div>
  );
}
