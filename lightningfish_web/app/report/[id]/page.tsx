import { AgentChat } from "@/components/AgentChat";
import { OpinionChart } from "@/components/OpinionChart";
import { DistributionBar } from "@/components/DistributionBar";
import type { SimulationResult } from "@/lib/types";
import { DOMAINS } from "@/lib/types";

async function getSimulation(id: string) {
  const pyUrl = process.env.PYTHON_SERVICE_URL ?? "http://localhost:8000";
  const res = await fetch(`${pyUrl}/simulate/${id}/result`, {
    cache: "no-store",
  });
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
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const sim = await getSimulation(id);

  if (!sim || sim.status !== "complete" || !sim.result_json) {
    return (
      <div className="max-w-xl mx-auto px-6 py-24 text-center">
        <p className="text-neutral-500 mb-4">
          {sim?.status === "running"
            ? "Simulation still running. Refresh in a moment."
            : "Report not found or simulation failed."}
        </p>
        <a
          href="/"
          className="text-sm text-neutral-700 underline underline-offset-2"
        >
          Back to home
        </a>
      </div>
    );
  }

  const result = sim.result_json;
  const domain = DOMAINS.find((d) => d.id === result.domain_id);
  const negativePole = domain?.negativePole ?? "Negative";
  const positivePole = domain?.positivePole ?? "Positive";
  const finalOpinion = result.trajectory[result.trajectory.length - 1] ?? 0;
  const opinionLabel =
    finalOpinion > 0.3
      ? positivePole
      : finalOpinion < -0.3
      ? negativePole
      : "Neutral";

  return (
    <div className="max-w-2xl mx-auto px-6 py-12">
      <div className="mb-8">
        <div className="flex items-center gap-2 mb-2">
          <span className="text-xs text-neutral-400 uppercase tracking-wider">
            {result.domain_id}
          </span>
          <span className="text-neutral-200">/</span>
          <span className="text-xs text-neutral-400">{result.event_type}</span>
        </div>
        <h1 className="text-2xl font-semibold mb-1">{result.seed_summary}</h1>
        <p className="text-sm text-neutral-500">
          {sim.n_agents} agents &middot; {sim.n_rounds} rounds &middot; $
          {sim.cost_usd.toFixed(4)} total cost
        </p>
      </div>

      <div className="border border-neutral-200 rounded-xl p-5 mb-5">
        <div className="flex items-center justify-between mb-1">
          <span className="text-xs font-medium text-neutral-400 uppercase tracking-wider">
            Consensus
          </span>
          <span
            className={`text-sm font-semibold ${
              finalOpinion > 0.3
                ? "text-emerald-600"
                : finalOpinion < -0.3
                ? "text-red-500"
                : "text-neutral-500"
            }`}
          >
            {opinionLabel} ({finalOpinion > 0 ? "+" : ""}
            {finalOpinion.toFixed(3)})
          </span>
        </div>
        <p className="text-xs text-neutral-400 mb-5">
          Scale: &minus;1.0 ({negativePole}) to +1.0 ({positivePole})
        </p>
        <OpinionChart
          trajectory={result.trajectory}
          negativePole={negativePole}
          positivePole={positivePole}
        />
      </div>

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

      <div className="border border-neutral-200 rounded-xl p-5 mb-5">
        <h2 className="text-xs font-medium text-neutral-400 uppercase tracking-wider mb-2">
          Simulation stats
        </h2>
        <dl className="grid grid-cols-2 gap-3 text-sm">
          <div>
            <dt className="text-neutral-400 text-xs">Total LLM calls</dt>
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
      </div>

      <div className="mb-5">
        <h2 className="text-xs font-medium text-neutral-400 uppercase tracking-wider mb-3">
          Interview an agent
        </h2>
        <AgentChat simulationId={id} domainId={result.domain_id} />
      </div>

      <div className="pt-4 border-t border-neutral-100 flex items-center justify-between text-sm">
        <a
          href="/history"
          className="text-neutral-500 hover:text-neutral-900 transition-colors"
        >
          &larr; All simulations
        </a>
        <a
          href="/"
          className="text-neutral-500 hover:text-neutral-900 transition-colors"
        >
          New simulation
        </a>
      </div>
    </div>
  );
}
