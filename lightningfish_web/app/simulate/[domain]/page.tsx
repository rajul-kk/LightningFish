"use client";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { useUser } from "@clerk/nextjs";
import { DOMAINS } from "@/lib/types";
import { createSimulation } from "@/lib/api";

const PRESETS = {
  fast: { n_agents: 100, n_rounds: 6 },
  balanced: { n_agents: 300, n_rounds: 10 },
  thorough: { n_agents: 600, n_rounds: 16 },
} as const;

const COST_PER_TIER1 = 0.003; // rough estimate per tier1 LLM call

function estimateCost(n_agents: number, n_rounds: number): string {
  const tier1PerRound = Math.max(1, Math.floor(n_agents * 0.1));
  const total = tier1PerRound * n_rounds * COST_PER_TIER1;
  return total.toFixed(3);
}

export default function SimulatePage() {
  const { domain } = useParams<{ domain: string }>();
  const router = useRouter();
  const { user } = useUser();

  const domainMeta = DOMAINS.find((d) => d.id === domain);

  const [rawInput, setRawInput] = useState("");
  const [nAgents, setNAgents] = useState(300);
  const [nRounds, setNRounds] = useState(10);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!domainMeta) {
    return (
      <div className="max-w-xl mx-auto px-6 py-24 text-neutral-500">
        Unknown domain: {domain}
      </div>
    );
  }

  function buildRawInput(): Record<string, unknown> {
    if (domain === "finance") {
      const lines = rawInput.trim().split("\n");
      const ticker = lines[0]?.trim().toUpperCase() ?? "";
      const filingText = lines.slice(1).join("\n").trim();
      return {
        ticker,
        filing_text: filingText || `Simulation for ${ticker}`,
        filing_date: new Date().toISOString().split("T")[0],
      };
    }
    return { pr_url: rawInput.trim() };
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const { simulation_id } = await createSimulation({
        domain_id: domain,
        user_id: user?.id ?? "anonymous",
        raw_input: buildRawInput(),
        n_agents: nAgents,
        n_rounds: nRounds,
      });
      router.push(`/simulate/${simulation_id}/live`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
      setLoading(false);
    }
  }

  return (
    <div className="max-w-xl mx-auto px-6 py-16">
      <div className="mb-8">
        <a
          href="/"
          className="text-sm text-neutral-400 hover:text-neutral-700 transition-colors"
        >
          &larr; Back
        </a>
        <h1 className="text-2xl font-semibold mt-4 mb-1">{domainMeta.label}</h1>
        <p className="text-neutral-500 text-sm">{domainMeta.description}</p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        <div>
          <label className="block text-sm font-medium mb-2">
            {domainMeta.inputLabel}
          </label>
          {domain === "finance" ? (
            <textarea
              className="w-full border border-neutral-200 rounded-lg px-4 py-3 text-sm focus:outline-none focus:border-neutral-400 resize-none"
              rows={5}
              placeholder={`AAPL\n\nApple reported Q4 earnings with revenue of $124B, beating analyst estimates by 3%...`}
              value={rawInput}
              onChange={(e) => setRawInput(e.target.value)}
              required
            />
          ) : (
            <input
              type="url"
              className="w-full border border-neutral-200 rounded-lg px-4 py-3 text-sm focus:outline-none focus:border-neutral-400"
              placeholder={domainMeta.inputPlaceholder}
              value={rawInput}
              onChange={(e) => setRawInput(e.target.value)}
              required
            />
          )}
          {domain === "finance" && (
            <p className="text-xs text-neutral-400 mt-1">
              First line: ticker symbol. Remaining lines: optional filing text or news excerpt.
            </p>
          )}
        </div>

        <div>
          <label className="block text-sm font-medium mb-3">
            Simulation parameters
          </label>
          <div className="flex gap-2 mb-4">
            {(Object.entries(PRESETS) as [keyof typeof PRESETS, typeof PRESETS[keyof typeof PRESETS]][]).map(
              ([key, preset]) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => {
                    setNAgents(preset.n_agents);
                    setNRounds(preset.n_rounds);
                  }}
                  className={`text-xs px-3 py-1.5 rounded border transition-colors ${
                    nAgents === preset.n_agents && nRounds === preset.n_rounds
                      ? "border-neutral-800 text-neutral-900 bg-neutral-50"
                      : "border-neutral-200 text-neutral-500 hover:border-neutral-400"
                  }`}
                >
                  {key.charAt(0).toUpperCase() + key.slice(1)}
                </button>
              )
            )}
          </div>
          <div className="space-y-3">
            <div>
              <div className="flex justify-between text-xs text-neutral-500 mb-1">
                <span>Agents</span>
                <span>{nAgents}</span>
              </div>
              <input
                type="range"
                min={50}
                max={1000}
                step={50}
                value={nAgents}
                onChange={(e) => setNAgents(Number(e.target.value))}
                className="w-full accent-neutral-800"
              />
            </div>
            <div>
              <div className="flex justify-between text-xs text-neutral-500 mb-1">
                <span>Rounds</span>
                <span>{nRounds}</span>
              </div>
              <input
                type="range"
                min={4}
                max={20}
                step={2}
                value={nRounds}
                onChange={(e) => setNRounds(Number(e.target.value))}
                className="w-full accent-neutral-800"
              />
            </div>
          </div>
          <p className="text-xs text-neutral-400 mt-2">
            Estimated cost: ~${estimateCost(nAgents, nRounds)}
          </p>
        </div>

        {error && (
          <p className="text-sm text-red-600 bg-red-50 border border-red-100 rounded-lg px-4 py-3">
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={loading}
          className="w-full bg-neutral-900 text-white text-sm font-medium py-3 rounded-lg hover:bg-neutral-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? "Starting simulation..." : "Run simulation"}
        </button>
      </form>
    </div>
  );
}
