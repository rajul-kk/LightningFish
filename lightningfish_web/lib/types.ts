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

export type DomainId = "finance" | "coding";

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

export interface DomainMeta {
  id: DomainId;
  label: string;
  description: string;
  negativePole: string;
  positivePole: string;
  inputLabel: string;
  inputPlaceholder: string;
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
  },
];
