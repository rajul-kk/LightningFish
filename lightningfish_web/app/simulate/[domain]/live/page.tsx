"use client";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { useSimulationStream } from "@/lib/use-sse";
import { OpinionChart } from "@/components/OpinionChart";
import { DistributionBar } from "@/components/DistributionBar";
import { RoundFeed } from "@/components/RoundFeed";
import { CostMeter } from "@/components/CostMeter";
import { BoltIcon } from "@/components/icons";
import type { SocialPost } from "@/lib/types";

const DEFAULT_NEGATIVE = "Negative";
const DEFAULT_POSITIVE = "Positive";

type PostWithRound = SocialPost & { round: number };

export default function LivePage() {
  // In this route, [domain] holds the simulation UUID (e.g. /simulate/{uuid}/live)
  const { domain: simulationId } = useParams<{ domain: string }>();
  const router = useRouter();
  const searchParams = useSearchParams();
  const totalRounds = Number(searchParams.get("rounds") ?? 12);
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

  return (
    <div className="max-w-2xl mx-auto px-6 py-12">
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="font-display text-xl text-fg">Simulation running</h1>
          <p className="text-sm text-fg-faint mt-1 font-mono">{simulationId}</p>
        </div>
        {isComplete && (
          <span className="pill-pos">
            Complete — redirecting...
          </span>
        )}
        {!isComplete && rounds.length > 0 && (
          <span className="flex items-center gap-1.5 text-xs text-fg-muted">
            <span className="inline-block w-1.5 h-1.5 rounded-full bg-glow shadow-[0_0_6px_rgba(63,235,184,0.8)] animate-pulse" />
            Live
          </span>
        )}
      </div>

      {error && (
        <div className="mb-6 text-sm text-coral bg-coral-dim border border-coral/25 rounded-xl px-4 py-3">
          {error}
        </div>
      )}

      <div className="space-y-6">
        <div className="surface p-5">
          <h2 className="eyebrow mb-4">
            Opinion trajectory
          </h2>
          <OpinionChart
            trajectory={trajectory}
            negativePole={DEFAULT_NEGATIVE}
            positivePole={DEFAULT_POSITIVE}
          />
        </div>

        <div className="surface p-5">
          <h2 className="eyebrow mb-4">
            Current distribution
          </h2>
          <DistributionBar
            distribution={distribution}
            negativePole={DEFAULT_NEGATIVE}
            positivePole={DEFAULT_POSITIVE}
          />
        </div>

        <div className="surface p-5">
          <h2 className="eyebrow mb-4">
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
          <div className="surface p-4 flex items-center justify-between text-sm">
            <div>
              <span className="eyebrow">Herding index</span>
              <div className="mt-1 font-display text-lg text-fg">
                {(latest.herding_index * 100).toFixed(0)}%
              </div>
              <div className="text-xs text-fg-faint">
                {(latest.herding_delta ?? 0) < -0.02
                  ? "Bifurcation — opinions diverging"
                  : latest.herding_index > 0.7
                  ? "Strong consensus forming"
                  : latest.herding_index > 0.5
                  ? "Moderate consensus"
                  : "Highly split"}
              </div>
            </div>
            {latest.cascade_detected && (
              <div className="text-right">
                <span className="pill-spark inline-flex items-center gap-1">
                  <BoltIcon className="w-3 h-3 drop-shadow-glow animate-bolt-flicker [will-change:opacity]" />
                  Cascade
                </span>
                {latest.cascade_trigger_archetype && (
                  <div className="text-xs text-fg-faint mt-1">{latest.cascade_trigger_archetype}</div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Post feed */}
        {postFeed.length > 0 && (
          <div className="surface p-5">
            <h2 className="eyebrow mb-3">
              Agent posts (live)
            </h2>
            <div className="space-y-2 max-h-72 overflow-y-auto">
              {postFeed.map((post, i) => (
                <div key={i} className="border border-ink-700 rounded-lg p-3 text-sm bg-ink-950/40">
                  <div className="flex flex-wrap gap-1.5 items-center mb-1.5">
                    <span className="font-medium text-xs text-fg-muted">{post.archetype}</span>
                    <span
                      className={
                        post.stance === "bullish" || post.stance === "approve"
                          ? "pill-pos !py-0.5 !px-1.5"
                          : "pill-neg !py-0.5 !px-1.5"
                      }
                    >
                      {post.stance}
                    </span>
                    <span className="text-xs bg-ink-800 text-fg-muted px-1.5 py-0.5 rounded-full">
                      {post.argument_tag}
                    </span>
                    <span className="text-xs text-fg-faint ml-auto font-mono">R{post.round}</span>
                  </div>
                  <p className="text-fg-muted text-xs leading-relaxed">{post.blurb}</p>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
