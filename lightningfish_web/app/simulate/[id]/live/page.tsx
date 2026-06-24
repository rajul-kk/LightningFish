"use client";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useRef } from "react";
import { useSimulationStream } from "@/lib/use-sse";
import { OpinionChart } from "@/components/OpinionChart";
import { DistributionBar } from "@/components/DistributionBar";
import { RoundFeed } from "@/components/RoundFeed";
import { CostMeter } from "@/components/CostMeter";

// Finance defaults — actual poles come from the simulation domain.
// The live page doesn't know the domain until it starts receiving events,
// so we use safe generic labels.
const DEFAULT_NEGATIVE = "Negative";
const DEFAULT_POSITIVE = "Positive";

export default function LivePage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const redirectedRef = useRef(false);

  const { rounds, isComplete, error, totalCost } = useSimulationStream(id ?? null);

  useEffect(() => {
    if (isComplete && !redirectedRef.current) {
      redirectedRef.current = true;
      router.push(`/report/${id}`);
    }
  }, [isComplete, id, router]);

  const trajectory = rounds.map((r) => r.mean_opinion);
  const latest = rounds[rounds.length - 1];
  const distribution = latest?.opinion_distribution ?? [];

  // Estimate total rounds from the first URL query param if available
  const totalRounds = 12; // fallback default shown in UI

  return (
    <div className="max-w-2xl mx-auto px-6 py-12">
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Simulation running</h1>
          <p className="text-sm text-neutral-400 mt-1 font-mono">{id}</p>
        </div>
        {isComplete && (
          <span className="text-xs font-medium text-emerald-600 bg-emerald-50 border border-emerald-100 px-3 py-1.5 rounded-full">
            Complete — redirecting...
          </span>
        )}
        {!isComplete && rounds.length > 0 && (
          <span className="flex items-center gap-1.5 text-xs text-neutral-500">
            <span className="inline-block w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
            Live
          </span>
        )}
      </div>

      {error && (
        <div className="mb-6 text-sm text-red-600 bg-red-50 border border-red-100 rounded-xl px-4 py-3">
          {error}
        </div>
      )}

      <div className="space-y-6">
        <div className="border border-neutral-200 rounded-xl p-5">
          <h2 className="text-xs font-medium text-neutral-400 uppercase tracking-wider mb-4">
            Opinion trajectory
          </h2>
          <OpinionChart
            trajectory={trajectory}
            negativePole={DEFAULT_NEGATIVE}
            positivePole={DEFAULT_POSITIVE}
          />
        </div>

        <div className="border border-neutral-200 rounded-xl p-5">
          <h2 className="text-xs font-medium text-neutral-400 uppercase tracking-wider mb-4">
            Current distribution
          </h2>
          <DistributionBar
            distribution={distribution}
            negativePole={DEFAULT_NEGATIVE}
            positivePole={DEFAULT_POSITIVE}
          />
        </div>

        <div className="border border-neutral-200 rounded-xl p-5">
          <h2 className="text-xs font-medium text-neutral-400 uppercase tracking-wider mb-4">
            Round activity
          </h2>
          <RoundFeed rounds={rounds} />
        </div>

        <CostMeter
          cost={rounds.reduce((s, r) => s + r.estimated_cost_usd, 0)}
          rounds={rounds.length}
          totalRounds={totalRounds}
        />
      </div>
    </div>
  );
}
