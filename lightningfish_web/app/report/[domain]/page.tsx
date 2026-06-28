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
        <p className="text-neutral-500 mb-4">
          {sim?.status === "running"
            ? "Simulation still running — refresh in a moment."
            : "Report not found or simulation failed."}
        </p>
        <Link href="/" className="text-sm text-neutral-700 underline underline-offset-2">
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
          <span className="text-xs text-neutral-400 uppercase tracking-wider">
            {result.domain_id}
          </span>
          <span className="text-neutral-200">/</span>
          <span className="text-xs text-neutral-400">{result.event_type?.replace(/_/g, " ")}</span>
        </div>
        <h1 className="text-2xl font-semibold mb-1">{result.seed_summary}</h1>
        <p className="text-xs text-neutral-400">
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
      <div className="border border-neutral-200 rounded-xl p-5 mb-5">
        <h2 className="text-xs font-medium text-neutral-400 uppercase tracking-wider mb-4">
          Opinion over time
        </h2>
        <OpinionChart
          trajectory={result.trajectory}
          negativePole={negativePole}
          positivePole={positivePole}
        />
      </div>

      {/* Distribution */}
      <div className="border border-neutral-200 rounded-xl p-5 mb-5">
        <h2 className="text-xs font-medium text-neutral-400 uppercase tracking-wider mb-4">
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
        <div className="border border-neutral-200 rounded-xl p-5 mb-5">
          <h2 className="text-xs font-medium text-neutral-400 uppercase tracking-wider mb-1">
            Herding index by round
          </h2>
          <p className="text-xs text-neutral-400 mb-4">
            0% = as diverse as round 1 &middot; 100% = full consensus &middot; negative = bifurcation
          </p>
          <div className="flex items-end gap-1 h-16">
            {result.herding_curve.map((h, i) => {
              const pct = Math.max(0, Math.min(100, h * 100));
              return (
                <div key={i} className="flex-1 flex flex-col items-center gap-1">
                  <div
                    className="w-full rounded-sm bg-amber-400"
                    style={{ height: `${pct}%`, minHeight: h < 0 ? 0 : 2 }}
                    title={`R${i + 1}: ${(h * 100).toFixed(0)}%`}
                  />
                </div>
              );
            })}
          </div>
          <div className="flex justify-between text-xs text-neutral-300 mt-1">
            <span>R1</span>
            <span>R{result.herding_curve.length}</span>
          </div>
        </div>
      )}

      {/* Argument emergence timeline */}
      {result.argument_timeline && Object.keys(result.argument_timeline).length > 0 && (
        <div className="border border-neutral-200 rounded-xl p-5 mb-5">
          <h2 className="text-xs font-medium text-neutral-400 uppercase tracking-wider mb-1">
            Argument emergence
          </h2>
          <p className="text-xs text-neutral-400 mb-3">
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
                  className="border border-neutral-100 rounded-lg px-2.5 py-1.5 text-xs"
                >
                  <span className="font-medium text-neutral-700">{tag}</span>
                  <span className="text-neutral-400 ml-1.5">R{round}</span>
                </div>
              ))}
          </div>
        </div>
      )}

      {/* Agent interview */}
      <div className="mb-5">
        <h2 className="text-xs font-medium text-neutral-400 uppercase tracking-wider mb-1">
          Ask an agent
        </h2>
        <p className="text-xs text-neutral-400 mb-3">
          Pick a persona and ask how they reasoned about this event.
        </p>
        <AgentChat simulationId={id} domainId={result.domain_id} />
      </div>

      {/* Stats — collapsed to secondary detail */}
      <details className="mb-5">
        <summary className="text-xs text-neutral-400 cursor-pointer hover:text-neutral-700 transition-colors">
          Simulation details
        </summary>
        <dl className="grid grid-cols-2 gap-3 text-sm mt-3 border border-neutral-100 rounded-xl p-4">
          <div>
            <dt className="text-neutral-400 text-xs">LLM calls</dt>
            <dd className="font-medium">{result.total_tier1_calls}</dd>
          </div>
          <div>
            <dt className="text-neutral-400 text-xs">Cost (USD)</dt>
            <dd className="font-medium">${sim.cost_usd.toFixed(5)}</dd>
          </div>
          <div>
            <dt className="text-neutral-400 text-xs">Rounds</dt>
            <dd className="font-medium">{result.trajectory.length}</dd>
          </div>
          <div>
            <dt className="text-neutral-400 text-xs">Population</dt>
            <dd className="font-medium">{sim.n_agents}</dd>
          </div>
        </dl>
      </details>

      {/* Footer nav */}
      <div className="pt-4 border-t border-neutral-100 flex items-center justify-between text-sm">
        <Link href="/history" className="text-neutral-400 hover:text-neutral-900 transition-colors">
          &larr; History
        </Link>
        <Link href="/" className="text-neutral-400 hover:text-neutral-900 transition-colors">
          New simulation
        </Link>
      </div>
    </div>
  );
}
