"use client";

interface Props {
  distribution: number[];
  negativePole: string;
  positivePole: string;
}

function buckets(distribution: number[]) {
  let negative = 0, neutral = 0, positive = 0;
  for (const v of distribution) {
    if (v < -0.2) negative++;
    else if (v > 0.2) positive++;
    else neutral++;
  }
  const total = distribution.length || 1;
  return {
    negative: (negative / total) * 100,
    neutral: (neutral / total) * 100,
    positive: (positive / total) * 100,
    counts: { negative, neutral, positive },
  };
}

export function DistributionBar({ distribution, negativePole, positivePole }: Props) {
  if (!distribution || distribution.length === 0) {
    return (
      <div className="h-3 rounded-full bg-ink-800" />
    );
  }

  const { negative, neutral, positive, counts } = buckets(distribution);

  return (
    <div>
      <div className="flex rounded-full overflow-hidden h-3 gap-px bg-ink-950">
        <div
          className="bg-coral transition-all duration-300"
          style={{ width: `${negative}%` }}
        />
        <div
          className="bg-ink-600 transition-all duration-300"
          style={{ width: `${neutral}%` }}
        />
        <div
          className="bg-glow shadow-[0_0_10px_rgba(63,235,184,0.5)] transition-all duration-300"
          style={{ width: `${positive}%` }}
        />
      </div>
      <div className="flex justify-between text-xs text-fg-faint mt-2 font-mono">
        <span>
          {negativePole} {counts.negative}
        </span>
        <span>Neutral {counts.neutral}</span>
        <span>
          {counts.positive} {positivePole}
        </span>
      </div>
    </div>
  );
}
