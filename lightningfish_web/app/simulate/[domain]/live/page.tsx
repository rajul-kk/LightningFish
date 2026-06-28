"use client";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { useSimulationStream } from "@/lib/use-sse";
import { OpinionChart } from "@/components/OpinionChart";
import { DistributionBar } from "@/components/DistributionBar";
import { RoundFeed } from "@/components/RoundFeed";
import { CostMeter } from "@/components/CostMeter";
import type { SocialPost } from "@/lib/types";

const DEFAULT_NEGATIVE = "Negative";
const DEFAULT_POSITIVE = "Positive";

type PostWithRound = SocialPost & { round: number };

export default function LivePage() {
  // In this route, [domain] holds the simulation UUID (e.g. /simulate/{uuid}/live)
  const { domain: simulationId } = useParams<{ domain: string }>();
  const router = useRouter();
  const redirectedRef = useRef(false);
  const [postFeed, setPostFeed] = useState<PostWithRound[]>([]);

  const { rounds, isComplete, error } = useSimulationStream(simulationId ?? null);

  useEffect(() => {
    if (isComplete && !redirectedRef.current) {
      redirectedRef.current = true;
      router.push(`/report/${simulationId}`);
    }
  }, [isComplete, simulationId, router]);

  // Accumulate posts from incoming rounds
  useEffect(() => {
    const latest = rounds[rounds.length - 1];
    if (!latest?.sample_posts?.length) return;
    const newPosts = latest.sample_posts.map((p) => ({ ...p, round: latest.round_number }));
    setPostFeed((prev) => [...newPosts, ...prev].slice(0, 30));
  }, [rounds]);

  const trajectory = rounds.map((r) => r.mean_opinion);
  const latest = rounds[rounds.length - 1];
  const distribution = latest?.opinion_distribution ?? [];

  const totalRounds = 12;

  return (
    <div className="max-w-2xl mx-auto px-6 py-12">
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Simulation running</h1>
          <p className="text-sm text-neutral-400 mt-1 font-mono">{simulationId}</p>
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

        {/* Herding indicator */}
        {latest?.herding_index !== undefined && (
          <div className="border border-neutral-200 rounded-xl p-4 flex items-center justify-between text-sm">
            <div>
              <span className="text-xs font-medium text-neutral-400 uppercase tracking-wider">Herding index</span>
              <div className="mt-1 font-semibold text-lg">
                {(latest.herding_index * 100).toFixed(0)}%
              </div>
              <div className="text-xs text-neutral-400">
                {latest.herding_index > 0.4
                  ? "Strong consensus forming"
                  : latest.herding_index < 0
                  ? "Bifurcation — opinions diverging"
                  : "Moderate diversity"}
              </div>
            </div>
            {latest.cascade_detected && (
              <div className="text-right">
                <span className="text-xs font-semibold text-amber-600 bg-amber-50 border border-amber-100 px-2 py-1 rounded-full">
                  ⚡ Cascade
                </span>
                {latest.cascade_trigger_archetype && (
                  <div className="text-xs text-neutral-400 mt-1">{latest.cascade_trigger_archetype}</div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Post feed */}
        {postFeed.length > 0 && (
          <div className="border border-neutral-200 rounded-xl p-5">
            <h2 className="text-xs font-medium text-neutral-400 uppercase tracking-wider mb-3">
              Agent posts (live)
            </h2>
            <div className="space-y-2 max-h-72 overflow-y-auto">
              {postFeed.map((post, i) => (
                <div key={i} className="border border-neutral-100 rounded-lg p-3 text-sm">
                  <div className="flex flex-wrap gap-1.5 items-center mb-1.5">
                    <span className="font-medium text-xs text-neutral-600">{post.archetype}</span>
                    <span
                      className={`text-xs px-1.5 py-0.5 rounded-full font-medium ${
                        post.stance === "bullish" || post.stance === "approve"
                          ? "bg-emerald-50 text-emerald-700"
                          : "bg-red-50 text-red-700"
                      }`}
                    >
                      {post.stance}
                    </span>
                    <span className="text-xs bg-neutral-100 text-neutral-600 px-1.5 py-0.5 rounded-full">
                      {post.argument_tag}
                    </span>
                    <span className="text-xs text-neutral-300 ml-auto">R{post.round}</span>
                  </div>
                  <p className="text-neutral-700 text-xs leading-relaxed">{post.blurb}</p>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
