import Link from "next/link";
import { OpinionChart } from "@/components/OpinionChart";
import { DistributionBar } from "@/components/DistributionBar";
import { ConsensusVerdict } from "@/components/ConsensusVerdict";

// Mock data — simulates a moderate bullish signal on an AAPL earnings beat
const MOCK = {
  seedSummary: "AAPL Q4 earnings beat — revenue $124.3B vs $122.6B consensus",
  eventType: "earnings_release",
  domainId: "finance",
  negativePole: "Bearish",
  positivePole: "Bullish",
  nAgents: 300,
  nRounds: 10,
  costUsd: 0.0412,
  totalTier1Calls: 290,
  // Trajectory: starts mildly negative as bears push back, then drifts bullish
  trajectory: [
    -0.04, 0.03, 0.10, 0.17, 0.24, 0.31, 0.37, 0.41, 0.43, 0.42,
  ],
  // 300-agent final distribution, skewed bullish
  finalDistribution: (() => {
    const agents: number[] = [];
    // ~170 bullish (0.2 – 0.9)
    for (let i = 0; i < 170; i++) agents.push(0.2 + (i / 170) * 0.7);
    // ~80 neutral (-0.2 – 0.2)
    for (let i = 0; i < 80; i++) agents.push(-0.2 + (i / 80) * 0.4);
    // ~50 bearish (-0.9 – -0.2)
    for (let i = 0; i < 50; i++) agents.push(-0.9 + (i / 50) * 0.7);
    return agents;
  })(),
};

export default function DemoReportPage() {
  const finalOpinion = MOCK.trajectory[MOCK.trajectory.length - 1];

  return (
    <div className="max-w-2xl mx-auto px-6 py-12">
      {/* Demo banner */}
      <div className="mb-6 px-4 py-2.5 bg-amber-50 border border-amber-200 rounded-lg flex items-center gap-2">
        <span className="text-amber-600 text-xs font-medium uppercase tracking-wide">
          Demo
        </span>
        <span className="text-amber-700 text-xs">
          This is a preview with mock data. No simulation was run.
        </span>
        <Link
          href="/simulate/finance"
          className="ml-auto text-xs text-amber-700 underline underline-offset-2 hover:text-amber-900 whitespace-nowrap"
        >
          Run a real one →
        </Link>
      </div>

      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center gap-2 mb-2">
          <span className="text-xs text-neutral-400 uppercase tracking-wider">
            {MOCK.domainId}
          </span>
          <span className="text-neutral-200">/</span>
          <span className="text-xs text-neutral-400">
            {MOCK.eventType.replace(/_/g, " ")}
          </span>
        </div>
        <h1 className="text-2xl font-semibold mb-1">{MOCK.seedSummary}</h1>
        <p className="text-xs text-neutral-400">
          {MOCK.nAgents} agents &middot; {MOCK.nRounds} rounds &middot; $
          {MOCK.costUsd.toFixed(4)}
        </p>
      </div>

      {/* Plain-English verdict */}
      <ConsensusVerdict
        finalOpinion={finalOpinion}
        trajectory={MOCK.trajectory}
        distribution={MOCK.finalDistribution}
        negativePole={MOCK.negativePole}
        positivePole={MOCK.positivePole}
        nAgents={MOCK.nAgents}
        eventType={MOCK.eventType}
      />

      {/* Trajectory chart */}
      <div className="border border-neutral-200 rounded-xl p-5 mb-5">
        <h2 className="text-xs font-medium text-neutral-400 uppercase tracking-wider mb-4">
          Opinion over time
        </h2>
        <OpinionChart
          trajectory={MOCK.trajectory}
          negativePole={MOCK.negativePole}
          positivePole={MOCK.positivePole}
        />
      </div>

      {/* Distribution */}
      <div className="border border-neutral-200 rounded-xl p-5 mb-5">
        <h2 className="text-xs font-medium text-neutral-400 uppercase tracking-wider mb-4">
          Final distribution
        </h2>
        <DistributionBar
          distribution={MOCK.finalDistribution}
          negativePole={MOCK.negativePole}
          positivePole={MOCK.positivePole}
        />
      </div>

      {/* Agent interview — disabled in demo */}
      <div className="mb-5 opacity-50">
        <h2 className="text-xs font-medium text-neutral-400 uppercase tracking-wider mb-1">
          Ask an agent
        </h2>
        <p className="text-xs text-neutral-400 mb-3">
          Available after running a real simulation.
        </p>
        <div className="border border-neutral-200 rounded-xl px-4 py-8 text-center">
          <p className="text-sm text-neutral-400">
            Agent chat requires a completed simulation.{" "}
            <Link
              href="/simulate/finance"
              className="underline underline-offset-2 hover:text-neutral-700"
            >
              Run one →
            </Link>
          </p>
        </div>
      </div>

      {/* Stats */}
      <details className="mb-5">
        <summary className="text-xs text-neutral-400 cursor-pointer hover:text-neutral-700 transition-colors">
          Simulation details
        </summary>
        <dl className="grid grid-cols-2 gap-3 text-sm mt-3 border border-neutral-100 rounded-xl p-4">
          <div>
            <dt className="text-neutral-400 text-xs">LLM calls</dt>
            <dd className="font-medium">{MOCK.totalTier1Calls}</dd>
          </div>
          <div>
            <dt className="text-neutral-400 text-xs">Cost (USD)</dt>
            <dd className="font-medium">${MOCK.costUsd.toFixed(5)}</dd>
          </div>
          <div>
            <dt className="text-neutral-400 text-xs">Rounds</dt>
            <dd className="font-medium">{MOCK.trajectory.length}</dd>
          </div>
          <div>
            <dt className="text-neutral-400 text-xs">Population</dt>
            <dd className="font-medium">{MOCK.nAgents}</dd>
          </div>
        </dl>
      </details>

      {/* Footer nav */}
      <div className="pt-4 border-t border-neutral-100 flex items-center justify-between text-sm">
        <Link
          href="/"
          className="text-neutral-400 hover:text-neutral-900 transition-colors"
        >
          &larr; Home
        </Link>
        <Link
          href="/simulate/finance"
          className="text-neutral-400 hover:text-neutral-900 transition-colors"
        >
          Run a real simulation →
        </Link>
      </div>
    </div>
  );
}
