interface Props {
  finalOpinion: number;
  trajectory: number[];
  distribution: number[];
  negativePole: string;
  positivePole: string;
  nAgents: number;
  eventType: string;
}

function bucketCounts(distribution: number[]) {
  let pos = 0, neg = 0;
  for (const v of distribution) {
    if (v > 0.2) pos++;
    else if (v < -0.2) neg++;
  }
  const total = distribution.length || 1;
  return {
    posPct: Math.round((pos / total) * 100),
    negPct: Math.round((neg / total) * 100),
    neutPct: Math.round(((total - pos - neg) / total) * 100),
  };
}

function strengthWord(abs: number) {
  if (abs > 0.65) return "strong";
  if (abs > 0.35) return "moderate";
  return "slight";
}

function buildSummary(
  finalOpinion: number,
  trajectory: number[],
  distribution: number[],
  negativePole: string,
  positivePole: string,
): string {
  const abs = Math.abs(finalOpinion);
  const { posPct, negPct, neutPct } = bucketCounts(distribution);
  const n = trajectory.length;

  if (abs < 0.15) {
    return (
      `After ${n} rounds the agent population remained genuinely split — ` +
      `${posPct}% leaned ${positivePole.toLowerCase()}, ${negPct}% leaned ` +
      `${negativePole.toLowerCase()}, and ${neutPct}% stayed neutral. ` +
      `No clear consensus formed.`
    );
  }

  const direction = finalOpinion > 0 ? positivePole.toLowerCase() : negativePole.toLowerCase();
  const strength = strengthWord(abs);

  // Did the population converge or start there?
  const first = trajectory[0] ?? 0;
  const moved = Math.abs(finalOpinion - first) > 0.12;
  const convergeWord = moved ? "converged toward" : "maintained";

  const dominant = finalOpinion > 0 ? posPct : negPct;
  const minority = finalOpinion > 0 ? negPct : posPct;

  return (
    `${dominant}% of agents ${convergeWord} a ${strength} ${direction} position ` +
    `over ${n} rounds. ${minority}% held the opposing view${minority < 10 ? " — a small but persistent minority" : ""}. ` +
    (abs > 0.6
      ? `The debate settled quickly and shows no sign of splitting.`
      : `The debate leans one way but isn't unanimous — a different framing could still shift it.`)
  );
}

export function ConsensusVerdict({
  finalOpinion,
  trajectory,
  distribution,
  negativePole,
  positivePole,
  eventType,
}: Props) {
  const abs = Math.abs(finalOpinion);
  const isPositive = finalOpinion > 0.15;
  const isNegative = finalOpinion < -0.15;

  const verdictColor = isPositive
    ? "border-glow/30 bg-glow-dim"
    : isNegative
    ? "border-coral/30 bg-coral-dim"
    : "border-ink-600 bg-ink-800";

  const labelColor = isPositive
    ? "text-glow"
    : isNegative
    ? "text-coral"
    : "text-fg-muted";

  const label = isPositive
    ? `${positivePole} — ${strengthWord(abs)} consensus`
    : isNegative
    ? `${negativePole} — ${strengthWord(abs)} consensus`
    : "No clear consensus";

  const summary = buildSummary(
    finalOpinion,
    trajectory,
    distribution,
    negativePole,
    positivePole,
  );

  return (
    <div className={`border rounded-2xl p-5 mb-5 ${verdictColor}`}>
      <div className="flex items-start justify-between gap-4 mb-2">
        <span className={`font-display text-lg ${labelColor}`}>{label}</span>
        <span className="text-xs text-fg-faint bg-ink-950 border border-ink-700 px-2.5 py-1 rounded-full whitespace-nowrap font-mono">
          {eventType.replace(/_/g, " ")}
        </span>
      </div>
      <p className="text-sm text-fg-muted leading-relaxed">{summary}</p>
    </div>
  );
}
