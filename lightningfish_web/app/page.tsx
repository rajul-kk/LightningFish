import Link from "next/link";
import { DOMAINS } from "@/lib/types";

export default function HomePage() {
  return (
    <div className="max-w-3xl mx-auto px-6 py-24">
      <div className="mb-16">
        <h1 className="text-4xl font-semibold tracking-tight mb-4">
          See how the market would react — before it does
        </h1>
        <p className="text-lg text-neutral-500 leading-relaxed max-w-xl">
          Enter a stock ticker or GitHub PR. Hundreds of calibrated AI personas
          — value investors, momentum traders, short sellers — deliberate in
          real time and converge on a collective verdict.
        </p>
        <p className="text-sm text-neutral-400 mt-3">
          Takes about 30 seconds. No account needed to view results.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {DOMAINS.map((domain) => (
          <Link
            key={domain.id}
            href={`/simulate/${domain.id}`}
            className="group border border-neutral-200 rounded-xl p-6 hover:border-neutral-400 transition-colors"
          >
            <div className="flex items-start justify-between mb-3">
              <span className="text-xs font-medium text-neutral-400 uppercase tracking-widest">
                {domain.id}
              </span>
              <span className="text-neutral-300 group-hover:text-neutral-500 transition-colors text-lg">
                &rarr;
              </span>
            </div>
            <h2 className="text-lg font-semibold mb-2">{domain.label}</h2>
            <p className="text-sm text-neutral-500 leading-relaxed">
              {domain.description}
            </p>
            <div className="mt-4 flex gap-3 text-xs text-neutral-400">
              <span className="bg-neutral-100 px-2 py-1 rounded">
                {domain.negativePole}
              </span>
              <span className="text-neutral-300">&harr;</span>
              <span className="bg-neutral-100 px-2 py-1 rounded">
                {domain.positivePole}
              </span>
            </div>
          </Link>
        ))}
      </div>

      <div className="mt-16 pt-8 border-t border-neutral-100">
        <p className="text-sm text-neutral-400">
          Built on calibrated behavioral archetypes grounded in academic
          literature.{" "}
          <Link
            href="/report/demo"
            className="text-neutral-700 underline underline-offset-2 hover:text-neutral-900"
          >
            Preview a sample report
          </Link>{" "}
          or{" "}
          <a
            href="/dev/keys"
            className="text-neutral-700 underline underline-offset-2 hover:text-neutral-900"
          >
            access via API
          </a>
          .
        </p>
      </div>
    </div>
  );
}
