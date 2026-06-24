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
      ? `The signal is clear and unlikely to reverse without new information.`
      : `The outcome is directional but not decisive — sentiment could shift on new developments.`)
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
    ? "border-emerald-200 bg-emerald-50"
    : isNegative
    ? "border-red-100 bg-red-50"
    : "border-neutral-200 bg-neutral-50";

  const labelColor = isPositive
    ? "text-emerald-700"
    : isNegative
    ? "text-red-600"
    : "text-neutral-600";

  const label = isPositive
    ? `${positivePole} — ${strengthWord(abs)} signal`
    : isNegative
    ? `${negativePole} — ${strengthWord(abs)} signal`
    : "No clear consensus";

  const summary = buildSummary(
    finalOpinion,
    trajectory,
    distribution,
    negativePole,
    positivePole,
  );

  return (
    <div className={`border rounded-xl p-5 mb-5 ${verdictColor}`}>
      <div className="flex items-start justify-between gap-4 mb-2">
        <span className={`text-base font-semibold ${labelColor}`}>{label}</span>
        <span className="text-xs text-neutral-400 bg-white border border-neutral-200 px-2 py-1 rounded-full whitespace-nowrap">
          {eventType.replace(/_/g, " ")}
        </span>
      </div>
      <p className="text-sm text-neutral-600 leading-relaxed">{summary}</p>
    </div>
  );
}
