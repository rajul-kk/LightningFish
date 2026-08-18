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
  if (v > 0.3) return "text-glow";
  if (v < -0.3) return "text-coral";
  return "text-fg-muted";
}

export function RoundFeed({ rounds }: Props) {
  const reversed = [...rounds].reverse();

  if (rounds.length === 0) {
    return (
      <div className="text-sm text-fg-faint py-8 text-center">
        Waiting for first round...
      </div>
    );
  }

  return (
    <div className="space-y-2.5 max-h-80 overflow-y-auto pr-1">
      {reversed.map((round) => (
        <div
          key={round.round_number}
          className="border border-ink-700 rounded-xl p-4 bg-ink-950/40"
        >
          <div className="flex items-center justify-between mb-2">
            <span className="eyebrow">
              Round {round.round_number}
            </span>
            <span className="text-xs text-fg-faint font-mono">
              {round.tier1_calls} LLM call{round.tier1_calls !== 1 ? "s" : ""}
              {" · "}${round.estimated_cost_usd.toFixed(4)}
            </span>
          </div>
          <div className="flex items-center gap-3">
            <span className={`text-sm font-medium font-mono ${opinionColor(round.mean_opinion)}`}>
              {round.mean_opinion > 0 ? "+" : ""}
              {round.mean_opinion.toFixed(3)}
            </span>
            <span className="text-xs text-fg-faint">
              {opinionLabel(round.mean_opinion)} — stddev{" "}
              {round.stddev_opinion.toFixed(3)}
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}
