import Link from "next/link";
import { DOMAINS } from "@/lib/types";

export default function HomePage() {
  return (
    <div className="max-w-4xl mx-auto px-6 py-24">
      {/* Hero */}
      <div className="mb-20 max-w-2xl">
        <p className="eyebrow text-glow mb-5 flex items-center gap-2">
          <span className="inline-block w-6 h-px bg-glow/60" />
          Multi-agent opinion simulation
        </p>
        <h1 className="font-display text-5xl sm:text-6xl leading-[1.05] tracking-tight text-fg mb-6">
          See how the crowd reacts{" "}
          <span className="italic text-glow">before it does</span>.
        </h1>
        <p className="text-lg text-fg-muted leading-relaxed max-w-xl">
          Enter a stock ticker, a GitHub PR, or a Hacker News link. A calibrated
          population of AI personas — investors, reviewers, cynics, lurkers —
          deliberates in real time and converges on a verdict.
        </p>
        <p className="text-sm text-fg-faint mt-4 font-mono">
          ~30s per run · no account needed to view results
        </p>
      </div>

      {/* Domain cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-20">
        {DOMAINS.map((domain, i) => (
          <Link
            key={domain.id}
            href={`/simulate/${domain.id}`}
            className="card-shine surface-interactive group relative p-6 overflow-hidden flex flex-col opacity-0 animate-fade-up hover:-translate-y-1"
            style={{ animationDelay: `${i * 110}ms` }}
          >
            <div className="flex items-start justify-between mb-4 relative">
              <span className="eyebrow text-fg-faint group-hover:text-glow transition-colors">
                {domain.id}
              </span>
              <span className="text-fg-faint group-hover:text-glow group-hover:translate-x-0.5 transition-all text-lg">
                &rarr;
              </span>
            </div>

            <h2 className="font-display text-xl text-fg mb-2 relative">
              {domain.label}
            </h2>
            <p className="text-sm text-fg-muted leading-relaxed mb-5 flex-1 relative">
              {domain.description}
            </p>

            <div className="flex items-center justify-between relative">
              <div className="flex items-center gap-2">
                <span className="pill-neg">{domain.negativePole}</span>
                <span className="text-fg-faint text-xs">&harr;</span>
                <span className="pill-pos">{domain.positivePole}</span>
              </div>
              <span className="flex items-center gap-1.5 text-xs text-fg-faint font-mono tabular-nums">
                <span className="relative flex w-1.5 h-1.5">
                  <span className="absolute inline-flex w-full h-full rounded-full bg-glow opacity-60 animate-ping" />
                  <span className="relative inline-flex w-1.5 h-1.5 rounded-full bg-glow" />
                </span>
                {domain.archetypes.length}
              </span>
            </div>
          </Link>
        ))}
      </div>

      {/* Footer */}
      <div className="pt-8 border-t border-ink-700 flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4">
        <p className="text-sm text-fg-faint">
          Built on calibrated behavioral archetypes. Coding and Hacker News
          are backtested against real settled outcomes — see each domain for
          results.
        </p>
        <div className="flex items-center gap-4 text-sm sm:ml-auto">
          <Link
            href="/report/demo"
            className="text-glow/90 hover:text-glow underline decoration-glow/30 hover:decoration-glow underline-offset-4 transition-colors whitespace-nowrap"
          >
            Preview a sample report
          </Link>
          <a
            href="/dev/keys"
            className="text-glow/90 hover:text-glow underline decoration-glow/30 hover:decoration-glow underline-offset-4 transition-colors whitespace-nowrap"
          >
            Access via API
          </a>
        </div>
      </div>
    </div>
  );
}
