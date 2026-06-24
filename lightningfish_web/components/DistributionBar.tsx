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
      <div className="h-4 rounded-full bg-neutral-100" />
    );
  }

  const { negative, neutral, positive, counts } = buckets(distribution);

  return (
    <div>
      <div className="flex rounded-full overflow-hidden h-3 gap-px">
        <div
          className="bg-red-400 transition-all duration-300"
          style={{ width: `${negative}%` }}
        />
        <div
          className="bg-neutral-200 transition-all duration-300"
          style={{ width: `${neutral}%` }}
        />
        <div
          className="bg-emerald-400 transition-all duration-300"
          style={{ width: `${positive}%` }}
        />
      </div>
      <div className="flex justify-between text-xs text-neutral-400 mt-1.5">
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
