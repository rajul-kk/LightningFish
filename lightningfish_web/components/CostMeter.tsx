"use client";

interface Props {
  cost: number;
  rounds: number;
  totalRounds: number;
}

export function CostMeter({ cost, rounds, totalRounds }: Props) {
  const pct = totalRounds > 0 ? (rounds / totalRounds) * 100 : 0;

  return (
    <div className="flex items-center gap-4 text-xs text-neutral-400">
      <div className="flex-1">
        <div className="flex justify-between mb-1">
          <span>Round {rounds} / {totalRounds}</span>
          <span className="tabular-nums">${cost.toFixed(4)}</span>
        </div>
        <div className="h-1 rounded-full bg-neutral-100">
          <div
            className="h-1 rounded-full bg-neutral-400 transition-all duration-500"
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>
    </div>
  );
}
