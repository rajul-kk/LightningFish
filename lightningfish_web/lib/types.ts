export interface RoundEvent {
  round_number: number;
  mean_opinion: number;
  stddev_opinion: number;
  tier1_calls: number;
  active_agent_ids: string[];
  estimated_cost_usd: number;
  opinion_distribution?: number[];
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
    label: "Market Sentiment",
    description:
      "Simulate how analyst archetypes react to earnings announcements, SEC filings, or market events.",
    negativePole: "Bearish",
    positivePole: "Bullish",
    inputLabel: "Ticker + event",
    inputPlaceholder: "e.g. AAPL, or paste a filing excerpt",
  },
  {
    id: "coding",
    label: "Code Review",
    description:
      "Simulate a multi-persona code review consensus for any GitHub pull request.",
    negativePole: "Block",
    positivePole: "Approve",
    inputLabel: "GitHub PR URL",
    inputPlaceholder: "https://github.com/owner/repo/pull/123",
  },
];
