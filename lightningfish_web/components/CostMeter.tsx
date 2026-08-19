"use client";

interface Props {
  cost: number;
  rounds: number;
  totalRounds: number;
}

export function CostMeter({ cost, rounds, totalRounds }: Props) {
  const pct = totalRounds > 0 ? (rounds / totalRounds) * 100 : 0;

  return (
    <div className="flex items-center gap-4 text-xs text-fg-faint">
      <div className="flex-1">
        <div className="flex justify-between mb-1.5 font-mono">
          {/* key remounts the span whenever the round advances, replaying the
              pop-in animation — a cheap way to make "the number changed"
              legible without a full charting/tween library. */}
          <span key={rounds} className="inline-block animate-value-pop">
            Round {rounds} / {totalRounds}
          </span>
          <span key={cost.toFixed(4)} className="inline-block tabular-nums text-fg-muted animate-value-pop">
            ${cost.toFixed(4)}
          </span>
        </div>
        <div className="h-1 rounded-full bg-ink-800">
          <div
            className="h-1 rounded-full bg-glow shadow-[0_0_6px_rgba(63,235,184,0.6)] transition-all duration-500"
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>
    </div>
  );
}
