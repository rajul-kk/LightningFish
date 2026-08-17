export interface SocialPost {
  agent_id: string;
  archetype: string;
  stance: string;
  argument_tag: string;
  confidence: number;
  blurb: string;
}

export interface RoundEvent {
  round_number: number;
  mean_opinion: number;
  stddev_opinion: number;
  tier1_calls: number;
  active_agent_ids: string[];
  estimated_cost_usd: number;
  opinion_distribution?: number[];
  // social fields (optional — present when social sim is running)
  herding_index?: number;
  herding_delta?: number;
  argument_diversity_score?: number;
  cascade_detected?: boolean;
  cascade_trigger_archetype?: string | null;
  new_argument_tags?: string[];
  sample_posts?: SocialPost[];
}

export interface SimulationCompleteEvent {
  type: "complete";
  simulation_id: string;
  total_cost_usd: number;
}

export interface SimulationErrorEvent {
  type: "error";
  message: string;
}

export type SSEMessage = RoundEvent | SimulationCompleteEvent | SimulationErrorEvent;

export interface SimulationResult {
  trajectory: number[];
  final_distribution: number[];
  total_tier1_calls: number;
  total_cost_usd: number;
  seed_summary: string;
  domain_id: string;
  event_type: string;
  // social sim fields (present when engine ran with social layer)
  herding_curve?: number[];
  argument_timeline?: Record<string, number>;
}

export interface Simulation {
  id: string;
  user_id: string;
  domain_id: string;
  status: "pending" | "running" | "complete" | "failed";
  seed_json: Record<string, unknown>;
  result_json: SimulationResult | null;
  cost_usd: number;
  created_at: string;
  n_agents: number;
  n_rounds: number;
}

export type DomainId = "finance" | "coding" | "hn";

export interface ModelOption {
  id: string;
  label: string;
  description: string;
  inputCostPerM: number;
  outputCostPerM: number;
}

export const MODELS: ModelOption[] = [
  {
    id: "claude-haiku-4-5-20251001",
    label: "Haiku 4.5",
    description: "Fast, lowest cost",
    inputCostPerM: 0.80,
    outputCostPerM: 4,
  },
  {
    id: "claude-sonnet-4-6",
    label: "Sonnet 4.6",
    description: "Balanced — default",
    inputCostPerM: 3,
    outputCostPerM: 15,
  },
  {
    id: "claude-opus-4-8",
    label: "Opus 4.8",
    description: "Most capable",
    inputCostPerM: 15,
    outputCostPerM: 75,
  },
];

export interface LocalStatus {
  available: boolean;
  gpu: boolean | null;
  models: string[];
}

export const LOCAL_POPULAR_MODELS = [
  "llama3.2",
  "llama3.1:8b",
  "mistral",
  "phi3",
  "gemma2:2b",
  "qwen2.5:7b",
] as const;

export const LOCAL_DEFAULT_BASE_URL = "http://localhost:11434/v1";

export interface ArchetypeMeta {
  name: string;
  defaultProportion: number;
  description: string;
}

export const FINANCE_ARCHETYPES: ArchetypeMeta[] = [
  { name: "ValueInvestor",        defaultProportion: 0.12, description: "Anchored to fundamentals, slow to move" },
  { name: "MomentumTrader",       defaultProportion: 0.18, description: "Trend follower, reactive to price moves" },
  { name: "RetailFOMO",           defaultProportion: 0.35, description: "Highly reactive, herding behavior" },
  { name: "ShortSeller",          defaultProportion: 0.05, description: "Contrarian; digs in when consensus rises" },
  { name: "InstitutionalAnalyst", defaultProportion: 0.10, description: "High influence, balanced conviction" },
  { name: "MacroTourist",         defaultProportion: 0.08, description: "Top-down macro lens, moderate reactivity" },
  { name: "PassiveLurker",        defaultProportion: 0.12, description: "Low influence, slow drift" },
];

export const CODING_ARCHETYPES: ArchetypeMeta[] = [
  { name: "SecurityReviewer",       defaultProportion: 0.10, description: "Blocks on security issues, high conviction" },
  { name: "PerformanceReviewer",    defaultProportion: 0.10, description: "Focused on runtime and memory impact" },
  { name: "StyleMaintainability",   defaultProportion: 0.20, description: "Cares about readability and consistency" },
  { name: "DomainExpertMaintainer", defaultProportion: 0.08, description: "Highest influence, domain ownership" },
  { name: "JuniorContributor",      defaultProportion: 0.40, description: "Deferential, follows senior signals" },
  { name: "CIBot",                  defaultProportion: 0.12, description: "Deterministic — CI pass rate only" },
];

export const HN_ARCHETYPES: ArchetypeMeta[] = [
  { name: "CasualLurkerVoter",     defaultProportion: 0.30, description: "Low-conviction upvoter, moderate herding" },
  { name: "EarlyAdopterHypeBeast", defaultProportion: 0.18, description: "Low resistance, amplifies early momentum" },
  { name: "ContrarianSkeptic",     defaultProportion: 0.15, description: "High resistance, pushes against the crowd" },
  { name: "DomainExpertPedant",    defaultProportion: 0.15, description: "High influence, technical scrutiny" },
  { name: "GreybeardCynic",        defaultProportion: 0.12, description: "Most resistant, strongly contrarian" },
  { name: "ShowHNFounder",         defaultProportion: 0.10, description: "Enthusiastic builder, high recency bias" },
];

export interface DomainMeta {
  id: DomainId;
  label: string;
  description: string;
  negativePole: string;
  positivePole: string;
  inputLabel: string;
  inputPlaceholder: string;
  /** Helper text under the input. */
  inputHint: string;
  /** Multi-line textarea rather than a single-line input. */
  multiline: boolean;
  archetypes: ArchetypeMeta[];
  example: { label: string; input: string };
  /** Turns the textbox contents into the adapter's raw_input payload. */
  buildRawInput: (raw: string) => Record<string, unknown>;
  /**
   * Shown alongside results when backtesting found the domain does not beat
   * its baselines. Being quiet about that would be overclaiming.
   */
  accuracyNote?: string;
}

/** Accepts a news.ycombinator.com item URL or a bare story id. */
function parseHnStoryId(raw: string): number {
  const trimmed = raw.trim();
  const fromUrl = trimmed.match(/[?&]id=(\d+)/);
  if (fromUrl) return Number(fromUrl[1]);
  const bare = trimmed.match(/^(\d+)$/);
  if (bare) return Number(bare[1]);
  return NaN;
}

export const DOMAINS: DomainMeta[] = [
  {
    id: "finance",
    label: "How will the market react?",
    description:
      "Enter any stock ticker — optionally add a news headline or earnings result. Value investors, traders, and retail buyers deliberate and reach a bullish or bearish verdict.",
    negativePole: "Bearish",
    positivePole: "Bullish",
    inputLabel: "Stock ticker",
    inputPlaceholder: "e.g. AAPL, or paste a news excerpt",
    inputHint:
      "First line: ticker (e.g. TSLA). Second line onwards: any context — or leave blank to use live headlines.",
    multiline: true,
    archetypes: FINANCE_ARCHETYPES,
    example: {
      label: "Try AAPL earnings",
      input:
        "AAPL\n\nApple beat Q4 earnings estimates, reporting revenue of $124.3B versus the $122.6B consensus. EPS came in at $1.64, above the $1.60 expected. iPhone sales surprised to the upside.",
    },
    buildRawInput: (raw) => {
      const lines = raw.trim().split("\n");
      const ticker = lines[0]?.trim().toUpperCase() ?? "";
      const filingText = lines.slice(1).join("\n").trim();
      return {
        ticker,
        filing_text: filingText || `Simulation for ${ticker}`,
        filing_date: new Date().toISOString().split("T")[0],
      };
    },
  },
  {
    id: "coding",
    label: "Should this PR be merged?",
    description:
      "Paste a GitHub pull request URL. Security reviewers, domain experts, and junior contributors weigh in and reach a consensus on whether to approve or block.",
    negativePole: "Block",
    positivePole: "Approve",
    inputLabel: "GitHub PR URL",
    inputPlaceholder: "https://github.com/owner/repo/pull/123",
    inputHint: "Any public GitHub pull request URL works.",
    multiline: false,
    archetypes: CODING_ARCHETYPES,
    example: {
      label: "Try an open-source PR",
      input: "https://github.com/pallets/flask/pull/5489",
    },
    buildRawInput: (raw) => ({ pr_url: raw.trim() }),
    accuracyNote:
      "Backtested on real merged/closed PRs, this domain does not beat a content-free baseline — the PR metadata a seed can see does not determine whether maintainers merge it. Read the deliberation, not the verdict.",
  },
  {
    id: "hn",
    label: "Will Hacker News upvote this?",
    description:
      "Paste a Hacker News story link. Lurkers, hype-beasts, cynics and domain pedants react in turn, herding or splitting as the thread develops.",
    negativePole: "Flop",
    positivePole: "Viral",
    inputLabel: "Hacker News story URL or ID",
    inputPlaceholder: "https://news.ycombinator.com/item?id=44281944",
    inputHint: "A news.ycombinator.com item link, or just the numeric story id.",
    multiline: false,
    archetypes: HN_ARCHETYPES,
    example: {
      label: "Try a front-page story",
      input: "https://news.ycombinator.com/item?id=44281944",
    },
    buildRawInput: (raw) => ({ story_id: parseHnStoryId(raw) }),
    accuracyNote:
      "Measured against 200 real stories, this simulation predicts reception at roughly chance (51.5%) while author karma alone reaches 62.5%. HN outcomes are driven by who posts and who replies early, not by what the model reads. Treat the output as a narrative, not a forecast.",
  },
];
