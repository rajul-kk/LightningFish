"use client";
import type { RoundEvent } from "@/lib/types";

interface Props {
  rounds: RoundEvent[];
}

function opinionLabel(v: number): string {
  if (v > 0.5) return "strongly positive";
  if (v > 0.1) return "positive";
  if (v < -0.5) return "strongly negative";
  if (v < -0.1) return "negative";
  return "neutral";
}

function opinionColor(v: number): string {
  if (v > 0.3) return "text-emerald-600";
  if (v < -0.3) return "text-red-500";
  return "text-neutral-500";
}

export function RoundFeed({ rounds }: Props) {
  const reversed = [...rounds].reverse();

  if (rounds.length === 0) {
    return (
      <div className="text-sm text-neutral-400 py-8 text-center">
        Waiting for first round...
      </div>
    );
  }

  return (
    <div className="space-y-3 max-h-80 overflow-y-auto pr-1">
      {reversed.map((round) => (
        <div
          key={round.round_number}
          className="border border-neutral-100 rounded-xl p-4"
        >
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold text-neutral-400 uppercase tracking-wider">
              Round {round.round_number}
            </span>
            <span className="text-xs text-neutral-300">
              {round.tier1_calls} LLM call{round.tier1_calls !== 1 ? "s" : ""}
              {" · "}${round.estimated_cost_usd.toFixed(4)}
            </span>
          </div>
          <div className="flex items-center gap-3">
            <span className={`text-sm font-medium ${opinionColor(round.mean_opinion)}`}>
              {round.mean_opinion > 0 ? "+" : ""}
              {round.mean_opinion.toFixed(3)}
            </span>
            <span className="text-xs text-neutral-400">
              {opinionLabel(round.mean_opinion)} — stddev{" "}
              {round.stddev_opinion.toFixed(3)}
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}
