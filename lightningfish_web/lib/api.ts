const PY = process.env.NEXT_PUBLIC_PYTHON_SERVICE_URL ?? "http://localhost:8000";
const SELF = typeof window !== "undefined" ? "" : (process.env.NEXT_PUBLIC_SELF_URL ?? "http://localhost:3000");

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${body}`);
  }
  return res.json() as Promise<T>;
}

export async function createSimulation(payload: {
  domain_id: string;
  user_id: string;
  raw_input: Record<string, unknown>;
  n_agents: number;
  n_rounds: number;
  model: string;
  agent_config: Record<string, number> | null;
  base_url?: string | null;
}): Promise<{ simulation_id: string }> {
  // Route through the Next.js API handler so SERVICE_SECRET stays server-side.
  const res = await fetch(`${SELF}/api/simulate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return json(res);
}

export function openSimulationStream(simulationId: string): EventSource {
  return new EventSource(`${PY}/simulate/${simulationId}`);
}

export async function chatWithAgent(
  simulationId: string,
  archetype: string,
  message: string
): Promise<{ reply: string }> {
  const res = await fetch(`${PY}/chat/${simulationId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ archetype, message }),
  });
  return json(res);
}

export async function getReport(simulationId: string) {
  const res = await fetch(`${PY}/simulate/${simulationId}/report`);
  return json(res);
}

export async function probeLocalServer(baseUrl: string): Promise<{
  available: boolean;
  gpu: boolean | null;
  models: string[];
}> {
  const res = await fetch(
    `${PY}/local/status?base_url=${encodeURIComponent(baseUrl)}`
  );
  return json(res);
}
