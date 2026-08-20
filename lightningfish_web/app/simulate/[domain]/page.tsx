"use client";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useUser } from "@clerk/nextjs";
import { HAS_CLERK } from "@/lib/clerk";
import {
  DOMAINS,
  MODELS,
  type ArchetypeMeta,
  type ModelOption,
  type LocalStatus,
  LOCAL_POPULAR_MODELS,
  LOCAL_DEFAULT_BASE_URL,
} from "@/lib/types";
import { createSimulation, probeLocalServer, probeServiceHealth, type ServiceHealth } from "@/lib/api";

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

/**
 * Auth is optional app-wide (see lib/clerk.ts): without a real Clerk key
 * there's no <ClerkProvider>, and calling useUser() without one throws
 * ("useUser can only be used within the <ClerkProvider />"). Unlike
 * /history and /dev/keys, this route is dynamic (no generateStaticParams),
 * so `next build` never prerenders it and doesn't catch the crash — it only
 * showed up navigating here at runtime. useUser() is only ever called from
 * WithClerkUser below, which only mounts when HAS_CLERK is true, so the hook
 * is always called on every render of whichever component owns it (rules of
 * hooks satisfied) while the page as a whole works with or without Clerk.
 */
export default function SimulatePage() {
  return HAS_CLERK ? <WithClerkUser /> : <SimulatePageBody userId="anonymous" />;
}

function WithClerkUser() {
  const { user } = useUser();
  return <SimulatePageBody userId={user?.id ?? "anonymous"} />;
}

function SimulatePageBody({ userId }: { userId: string }) {
  const { domain } = useParams<{ domain: string }>();
  const router = useRouter();

  const domainMeta = DOMAINS.find((d) => d.id === domain);
  // Empty (not a fallback to another domain's list) when the id is unknown:
  // the hooks below run before the guard, and silently showing some other
  // domain's archetypes is worse than showing none.
  const archetypes = domainMeta?.archetypes ?? [];

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
  const [useLocalModel, setUseLocalModel] = useState(false);
  const [localBaseUrl, setLocalBaseUrl] = useState(LOCAL_DEFAULT_BASE_URL);
  const [localModelName, setLocalModelName] = useState("qwen2.5:7b");
  const [localStatus, setLocalStatus] = useState<LocalStatus | null>(null);
  const [probingLocal, setProbingLocal] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Hosted models (Haiku/Sonnet/Opus) call out to the Python backend, which
  // needs both to be reachable and to have ANTHROPIC_API_KEY set. Neither is
  // guaranteed on a fresh clone or a paused deployment — without this check
  // the picker shows three costed, seemingly-live options that fail on the
  // first real request with no warning beforehand.
  const [hostedStatus, setHostedStatus] = useState<ServiceHealth | null>(null);
  useEffect(() => {
    let cancelled = false;
    probeServiceHealth().then((s) => {
      if (!cancelled) setHostedStatus(s);
    });
    return () => {
      cancelled = true;
    };
  }, []);
  const hostedAvailable = hostedStatus === null || (hostedStatus.reachable && hostedStatus.anthropicConfigured);

  if (!domainMeta) {
    return (
      <div className="max-w-xl mx-auto px-6 py-24 text-fg-muted">
        Unknown domain: {domain}
      </div>
    );
  }
  // Narrowed alias so the handlers below don't each need a null check.
  const meta = domainMeta;

  async function probeLocal() {
    setProbingLocal(true);
    setLocalStatus(null);
    try {
      const status = await probeLocalServer(localBaseUrl);
      setLocalStatus(status);
    } catch {
      setLocalStatus({ available: false, gpu: null, models: [] });
    }
    setProbingLocal(false);
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
    return meta.buildRawInput(rawInput);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    // The model buttons disable themselves when hosted is unavailable, but
    // `model` still holds whatever was selected before that state resolved
    // (the Sonnet default, on first load) - without this check that stale
    // selection would silently submit and fail on the backend instead of
    // here, where there's actually enough context to say why.
    if (!useLocalModel && !hostedAvailable) {
      setError(
        !hostedStatus?.reachable
          ? "Can't reach the Python backend. Start it, or switch to local inference below."
          : "No ANTHROPIC_API_KEY configured on the backend. Switch to local inference below, or set one."
      );
      return;
    }
    setLoading(true);
    try {
      const agent_config = normalizedConfig(archetypes, enabled, customProps);
      const { simulation_id } = await createSimulation({
        domain_id: domain,
        user_id: userId,
        raw_input: buildRawInput(),
        n_agents: nAgents,
        n_rounds: nRounds,
        model: useLocalModel ? `ollama:${localModelName}` : model.id,
        agent_config,
        base_url: useLocalModel ? localBaseUrl : null,
      });
      router.push(`/simulate/${simulation_id}/live?rounds=${nRounds}`);
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
        <Link href="/" className="text-sm text-fg-faint hover:text-glow transition-colors">
          &larr; Back
        </Link>
        <h1 className="font-display text-3xl text-fg mt-4 mb-1">{meta.label}</h1>
        <p className="text-fg-muted text-sm">{meta.description}</p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-7">
        {/* Seed input */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <label className="text-sm font-medium text-fg">{meta.inputLabel}</label>
            {meta.example && (
              <button
                type="button"
                onClick={() => setRawInput(meta.example.input)}
                className="text-xs text-fg-faint hover:text-glow underline decoration-fg-faint/40 hover:decoration-glow underline-offset-2 transition-colors"
              >
                {meta.example.label}
              </button>
            )}
          </div>
          {meta.multiline ? (
            <textarea
              className="field resize-none"
              rows={5}
              placeholder={meta.inputPlaceholder}
              value={rawInput}
              onChange={(e) => setRawInput(e.target.value)}
              required
            />
          ) : (
            <input
              type="text"
              className="field"
              placeholder={meta.inputPlaceholder}
              value={rawInput}
              onChange={(e) => setRawInput(e.target.value)}
              required
            />
          )}
          <p className="text-xs text-fg-faint mt-1.5">{meta.inputHint}</p>
          <p className="text-xs text-spark bg-spark-dim border border-spark/25 rounded-lg px-3 py-2.5 mt-3 leading-relaxed">
            <span className="font-semibold">Validation: </span>
            {meta.validationNote}
          </p>
        </div>

        {/* Simulation parameters */}
        <div>
          <label className="eyebrow block mb-3">Parameters</label>
          <div className="flex gap-2 mb-4">
            {(Object.entries(PRESETS) as [keyof typeof PRESETS, (typeof PRESETS)[keyof typeof PRESETS]][]).map(
              ([key, preset]) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => { setNAgents(preset.n_agents); setNRounds(preset.n_rounds); }}
                  className={`text-xs px-3 py-1.5 rounded-lg border transition-colors ${
                    nAgents === preset.n_agents && nRounds === preset.n_rounds
                      ? "border-glow/50 text-glow bg-glow-dim"
                      : "border-ink-600 text-fg-muted hover:border-ink-500"
                  }`}
                >
                  {key.charAt(0).toUpperCase() + key.slice(1)}
                </button>
              )
            )}
          </div>
          <div className="space-y-4">
            <div>
              <div className="flex justify-between text-xs text-fg-muted mb-1.5">
                <span>Agents</span><span className="font-mono text-fg">{nAgents}</span>
              </div>
              <input type="range" min={50} max={1000} step={50} value={nAgents}
                onChange={(e) => setNAgents(Number(e.target.value))}
                className="w-full" />
            </div>
            <div>
              <div className="flex justify-between text-xs text-fg-muted mb-1.5">
                <span>Rounds</span><span className="font-mono text-fg">{nRounds}</span>
              </div>
              <input type="range" min={4} max={20} step={2} value={nRounds}
                onChange={(e) => setNRounds(Number(e.target.value))}
                className="w-full" />
            </div>
          </div>
        </div>

        {/* Model picker */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <label className="eyebrow">Model</label>
            {hostedStatus !== null && !hostedAvailable && (
              <span className="pill-neg !py-0.5 !px-2">
                {!hostedStatus.reachable ? "backend offline" : "no API key configured"}
              </span>
            )}
          </div>
          <div className="grid grid-cols-3 gap-2">
            {MODELS.map((m) => (
              <button
                key={m.id}
                type="button"
                disabled={!hostedAvailable}
                onClick={() => setModel(m)}
                className={`text-left px-3 py-2.5 rounded-lg border text-sm transition-colors ${
                  !hostedAvailable
                    ? "border-ink-700 opacity-40 cursor-not-allowed"
                    : model.id === m.id
                    ? "border-glow/50 bg-glow-dim"
                    : "border-ink-700 hover:border-ink-500"
                }`}
              >
                <div className="font-medium text-xs text-fg">{m.label}</div>
                <div className="text-fg-faint text-xs mt-0.5">{m.description}</div>
                <div className="text-fg-faint/70 text-xs mt-1 font-mono">${m.inputCostPerM}/M</div>
              </button>
            ))}
          </div>
          {hostedAvailable ? (
            <p className="text-xs text-fg-faint mt-2 font-mono">
              Estimated cost: ~${estimateCost(nAgents, nRounds, model)}
            </p>
          ) : (
            <p className="text-xs text-spark mt-2">
              {!hostedStatus?.reachable
                ? "Can't reach the Python backend — hosted models are unavailable until it's running."
                : "The backend has no ANTHROPIC_API_KEY set — hosted models will fail on the first request."}
              {" "}Use local inference below instead.
            </p>
          )}
        </div>

        {/* Local / Self-hosted */}
        <div>
          <label className="eyebrow block mb-2">
            Run on your own GPU / CPU
          </label>
          <div className="surface overflow-hidden">
            <div className="flex items-center gap-3 px-4 py-3">
              <input
                type="checkbox"
                id="use-local"
                checked={useLocalModel}
                onChange={(e) => {
                  setUseLocalModel(e.target.checked);
                  setLocalStatus(null);
                }}
              />
              <label
                htmlFor="use-local"
                className="text-sm text-fg flex-1 cursor-pointer"
              >
                Use local inference server (Ollama)
              </label>
              {useLocalModel && localStatus && (
                <span
                  className={
                    !localStatus.available
                      ? "pill-neg"
                      : localStatus.gpu
                      ? "pill-pos"
                      : "pill-neutral"
                  }
                >
                  {!localStatus.available
                    ? "offline"
                    : localStatus.gpu
                    ? "GPU"
                    : "CPU"}
                </span>
              )}
            </div>

            {useLocalModel && (
              <div className="border-t border-ink-700 px-4 py-3 space-y-3">
                <div>
                  <label className="block text-xs text-fg-muted mb-1">
                    Endpoint
                  </label>
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={localBaseUrl}
                      onChange={(e) => {
                        setLocalBaseUrl(e.target.value);
                        setLocalStatus(null);
                      }}
                      className="field flex-1 py-2"
                      placeholder="http://localhost:11434/v1"
                    />
                    <button
                      type="button"
                      onClick={probeLocal}
                      disabled={probingLocal}
                      className="btn-ghost text-xs px-3 py-2 whitespace-nowrap"
                    >
                      {probingLocal ? "..." : "Test"}
                    </button>
                  </div>
                  {localStatus && !localStatus.available && (
                    <p className="text-xs text-coral mt-1.5">
                      Could not reach server. Is Ollama running?
                    </p>
                  )}
                </div>

                <div>
                  <label className="block text-xs text-fg-muted mb-1">
                    Model
                  </label>
                  <div className="flex gap-1.5 flex-wrap mb-2">
                    {LOCAL_POPULAR_MODELS.map((m) => (
                      <button
                        key={m}
                        type="button"
                        onClick={() => setLocalModelName(m)}
                        className={`text-xs px-2 py-1 rounded border transition-colors font-mono ${
                          localModelName === m
                            ? "border-glow/50 bg-glow-dim text-glow"
                            : "border-ink-600 text-fg-muted hover:border-ink-500"
                        }`}
                      >
                        {m}
                      </button>
                    ))}
                  </div>
                  <input
                    type="text"
                    value={localModelName}
                    onChange={(e) => setLocalModelName(e.target.value)}
                    className="field py-2 font-mono"
                    placeholder="Custom model name"
                  />
                </div>

                {localStatus?.models.length ? (
                  <p className="text-xs text-fg-faint">
                    Loaded: {localStatus.models.join(", ")}
                  </p>
                ) : null}

                <p className="text-xs text-fg-faint leading-relaxed">
                  Zero API cost. Install Ollama at{" "}
                  <a
                    href="https://ollama.com"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-glow/90 underline decoration-glow/30 underline-offset-2 hover:text-glow"
                  >
                    ollama.com
                  </a>
                  {", then run "}
                  <code className="bg-ink-800 text-fg px-1.5 py-0.5 rounded font-mono">
                    ollama pull qwen2.5:7b
                  </code>
                  . Smaller models (llama3.2 and below) tend to drop the
                  structured output format under load.
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Advanced: Agent mix */}
        <div>
          <button
            type="button"
            onClick={() => setShowAdvanced((v) => !v)}
            className="flex items-center gap-1.5 text-sm text-fg-muted hover:text-fg transition-colors"
          >
            <span className="text-xs text-glow">{showAdvanced ? "▾" : "▸"}</span>
            Agent mix
            {enabled.size < archetypes.length && (
              <span className="text-xs text-fg-faint">
                ({enabled.size}/{archetypes.length} active)
              </span>
            )}
          </button>

          {showAdvanced && (
            <div className="mt-3 surface overflow-hidden">
              <div className="divide-y divide-ink-700">
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
                        />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center justify-between">
                            <span className="text-sm font-medium text-fg">{a.name}</span>
                            <span className="text-xs text-glow font-mono tabular-nums">
                              {isOn ? Math.round((prop / (totalEnabled || 1)) * 100) : 0}%
                            </span>
                          </div>
                          <p className="text-xs text-fg-faint truncate">{a.description}</p>
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
                          className="w-full mt-2.5"
                        />
                      )}
                    </div>
                  );
                })}
              </div>
              <div className="px-4 py-2.5 bg-ink-950/40 border-t border-ink-700">
                <p className="text-xs text-fg-faint">
                  Proportions are normalized at run time. Disabling an archetype removes it entirely.
                </p>
              </div>
            </div>
          )}
        </div>

        {error && (
          <p className="text-sm text-coral bg-coral-dim border border-coral/25 rounded-lg px-4 py-3">
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={loading}
          className="btn-primary w-full text-sm"
        >
          {loading ? "Starting simulation..." : "Run simulation"}
        </button>
      </form>
    </div>
  );
}
