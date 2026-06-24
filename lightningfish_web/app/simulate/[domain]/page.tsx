"use client";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { useUser } from "@clerk/nextjs";
import {
  DOMAINS,
  MODELS,
  FINANCE_ARCHETYPES,
  CODING_ARCHETYPES,
  type ArchetypeMeta,
  type ModelOption,
} from "@/lib/types";
import { createSimulation } from "@/lib/api";

const PRESETS = {
  fast:     { n_agents: 100, n_rounds: 6  },
  balanced: { n_agents: 300, n_rounds: 10 },
  thorough: { n_agents: 600, n_rounds: 16 },
} as const;

function estimateCost(n_agents: number, n_rounds: number, model: ModelOption): string {
  const tier1PerRound = Math.max(1, Math.floor(n_agents * 0.1));
  // Rough: avg 400 input tokens + 4 output tokens per tier-1 call
  const inputCost  = tier1PerRound * n_rounds * 400  * (model.inputCostPerM  / 1_000_000);
  const outputCost = tier1PerRound * n_rounds * 4    * (model.outputCostPerM / 1_000_000);
  return (inputCost + outputCost).toFixed(3);
}

const EXAMPLES: Record<string, { label: string; input: string }> = {
  finance: {
    label: "Try AAPL earnings",
    input: "AAPL\n\nApple beat Q4 earnings estimates, reporting revenue of $124.3B versus the $122.6B consensus. EPS came in at $1.64, above the $1.60 expected. iPhone sales surprised to the upside.",
  },
  coding: {
    label: "Try an open-source PR",
    input: "https://github.com/pallets/flask/pull/5489",
  },
};

function normalizedConfig(
  archetypes: ArchetypeMeta[],
  enabled: Set<string>,
  customProps: Record<string, number>
): Record<string, number> | null {
  const active = archetypes.filter((a) => enabled.has(a.name));
  if (active.length === archetypes.length) return null; // all on = use defaults
  const raw = Object.fromEntries(
    active.map((a) => [a.name, customProps[a.name] ?? a.defaultProportion])
  );
  const total = Object.values(raw).reduce((s, v) => s + v, 0) || 1;
  return Object.fromEntries(Object.entries(raw).map(([k, v]) => [k, v / total]));
}

export default function SimulatePage() {
  const { domain } = useParams<{ domain: string }>();
  const router = useRouter();
  const { user } = useUser();

  const domainMeta = DOMAINS.find((d) => d.id === domain);
  const archetypes = domain === "finance" ? FINANCE_ARCHETYPES : CODING_ARCHETYPES;

  const [rawInput, setRawInput] = useState("");
  const [nAgents, setNAgents] = useState(300);
  const [nRounds, setNRounds] = useState(10);
  const [model, setModel] = useState(MODELS[1]); // Sonnet default
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [enabled, setEnabled] = useState<Set<string>>(
    () => new Set(archetypes.map((a) => a.name))
  );
  const [customProps, setCustomProps] = useState<Record<string, number>>(
    () => Object.fromEntries(archetypes.map((a) => [a.name, a.defaultProportion]))
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!domainMeta) {
    return (
      <div className="max-w-xl mx-auto px-6 py-24 text-neutral-500">
        Unknown domain: {domain}
      </div>
    );
  }

  function toggleArchetype(name: string) {
    setEnabled((prev) => {
      const next = new Set(prev);
      if (next.has(name)) {
        if (next.size <= 1) return prev; // keep at least one
        next.delete(name);
      } else {
        next.add(name);
      }
      return next;
    });
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
      const agent_config = normalizedConfig(archetypes, enabled, customProps);
      const { simulation_id } = await createSimulation({
        domain_id: domain,
        user_id: user?.id ?? "anonymous",
        raw_input: buildRawInput(),
        n_agents: nAgents,
        n_rounds: nRounds,
        model: model.id,
        agent_config,
      });
      router.push(`/simulate/${simulation_id}/live`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
      setLoading(false);
    }
  }

  const totalEnabled = archetypes
    .filter((a) => enabled.has(a.name))
    .reduce((s, a) => s + (customProps[a.name] ?? a.defaultProportion), 0);

  return (
    <div className="max-w-xl mx-auto px-6 py-16">
      <div className="mb-8">
        <a href="/" className="text-sm text-neutral-400 hover:text-neutral-700 transition-colors">
          &larr; Back
        </a>
        <h1 className="text-2xl font-semibold mt-4 mb-1">{domainMeta.label}</h1>
        <p className="text-neutral-500 text-sm">{domainMeta.description}</p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Seed input */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <label className="text-sm font-medium">{domainMeta.inputLabel}</label>
            {EXAMPLES[domain] && (
              <button
                type="button"
                onClick={() => setRawInput(EXAMPLES[domain].input)}
                className="text-xs text-neutral-400 hover:text-neutral-700 underline underline-offset-2 transition-colors"
              >
                {EXAMPLES[domain].label}
              </button>
            )}
          </div>
          {domain === "finance" ? (
            <textarea
              className="w-full border border-neutral-200 rounded-lg px-4 py-3 text-sm focus:outline-none focus:border-neutral-400 resize-none"
              rows={5}
              placeholder={"AAPL\n\nOptional: paste any news, filing excerpt, or earnings summary. Leave blank and we'll use recent headlines automatically."}
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
          <p className="text-xs text-neutral-400 mt-1">
            {domain === "finance"
              ? "First line: ticker (e.g. TSLA). Second line onwards: any context — or leave blank to use live headlines."
              : "Any public GitHub pull request URL works."}
          </p>
        </div>

        {/* Simulation parameters */}
        <div>
          <label className="block text-sm font-medium mb-3">Parameters</label>
          <div className="flex gap-2 mb-4">
            {(Object.entries(PRESETS) as [keyof typeof PRESETS, (typeof PRESETS)[keyof typeof PRESETS]][]).map(
              ([key, preset]) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => { setNAgents(preset.n_agents); setNRounds(preset.n_rounds); }}
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
                <span>Agents</span><span>{nAgents}</span>
              </div>
              <input type="range" min={50} max={1000} step={50} value={nAgents}
                onChange={(e) => setNAgents(Number(e.target.value))}
                className="w-full accent-neutral-800" />
            </div>
            <div>
              <div className="flex justify-between text-xs text-neutral-500 mb-1">
                <span>Rounds</span><span>{nRounds}</span>
              </div>
              <input type="range" min={4} max={20} step={2} value={nRounds}
                onChange={(e) => setNRounds(Number(e.target.value))}
                className="w-full accent-neutral-800" />
            </div>
          </div>
        </div>

        {/* Model picker */}
        <div>
          <label className="block text-sm font-medium mb-2">Model</label>
          <div className="grid grid-cols-3 gap-2">
            {MODELS.map((m) => (
              <button
                key={m.id}
                type="button"
                onClick={() => setModel(m)}
                className={`text-left px-3 py-2.5 rounded-lg border text-sm transition-colors ${
                  model.id === m.id
                    ? "border-neutral-800 bg-neutral-50"
                    : "border-neutral-200 hover:border-neutral-400"
                }`}
              >
                <div className="font-medium text-xs">{m.label}</div>
                <div className="text-neutral-400 text-xs mt-0.5">{m.description}</div>
                <div className="text-neutral-300 text-xs mt-1">${m.inputCostPerM}/M</div>
              </button>
            ))}
          </div>
          <p className="text-xs text-neutral-400 mt-2">
            Estimated cost: ~${estimateCost(nAgents, nRounds, model)}
          </p>
        </div>

        {/* Advanced: Agent mix */}
        <div>
          <button
            type="button"
            onClick={() => setShowAdvanced((v) => !v)}
            className="flex items-center gap-1.5 text-sm text-neutral-500 hover:text-neutral-800 transition-colors"
          >
            <span className="text-xs">{showAdvanced ? "▾" : "▸"}</span>
            Agent mix
            {enabled.size < archetypes.length && (
              <span className="text-xs text-neutral-400">
                ({enabled.size}/{archetypes.length} active)
              </span>
            )}
          </button>

          {showAdvanced && (
            <div className="mt-3 border border-neutral-200 rounded-xl overflow-hidden">
              <div className="divide-y divide-neutral-100">
                {archetypes.map((a) => {
                  const isOn = enabled.has(a.name);
                  const prop = customProps[a.name] ?? a.defaultProportion;
                  return (
                    <div
                      key={a.name}
                      className={`px-4 py-3 transition-colors ${isOn ? "" : "opacity-40"}`}
                    >
                      <div className="flex items-center gap-3">
                        <input
                          type="checkbox"
                          checked={isOn}
                          onChange={() => toggleArchetype(a.name)}
                          className="accent-neutral-800"
                        />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center justify-between">
                            <span className="text-sm font-medium">{a.name}</span>
                            <span className="text-xs text-neutral-400 tabular-nums">
                              {isOn ? Math.round((prop / (totalEnabled || 1)) * 100) : 0}%
                            </span>
                          </div>
                          <p className="text-xs text-neutral-400 truncate">{a.description}</p>
                        </div>
                      </div>
                      {isOn && (
                        <input
                          type="range"
                          min={0.01}
                          max={0.80}
                          step={0.01}
                          value={prop}
                          onChange={(e) =>
                            setCustomProps((prev) => ({
                              ...prev,
                              [a.name]: Number(e.target.value),
                            }))
                          }
                          className="w-full mt-2 accent-neutral-600"
                        />
                      )}
                    </div>
                  );
                })}
              </div>
              <div className="px-4 py-2.5 bg-neutral-50 border-t border-neutral-100">
                <p className="text-xs text-neutral-400">
                  Proportions are normalized at run time. Disabling an archetype removes it entirely.
                </p>
              </div>
            </div>
          )}
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
