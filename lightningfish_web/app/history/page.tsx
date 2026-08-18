import Link from "next/link";
import { auth } from "@clerk/nextjs/server";
import { HAS_CLERK } from "@/lib/clerk";

async function getHistory(userId: string) {
  const pyUrl = process.env.PYTHON_SERVICE_URL ?? "http://localhost:8000";
  const res = await fetch(`${pyUrl}/simulate?user_id=${userId}&limit=50`, {
    cache: "no-store",
  });
  if (!res.ok) return [];
  return res.json() as Promise<
    Array<{
      id: string;
      domain_id: string;
      status: string;
      cost_usd: number;
      created_at: string;
      result_json: { seed_summary?: string; event_type?: string } | null;
    }>
  >;
}

function statusBadge(status: string) {
  if (status === "complete") {
    return <span className="pill-pos">complete</span>;
  }
  if (status === "running") {
    return <span className="pill-spark">running</span>;
  }
  return <span className="pill-neutral">{status}</span>;
}

export default async function HistoryPage() {
  // Same contract as the layout: without Clerk configured there is no provider
  // and no auth() to call, so degrade to a notice instead of throwing.
  if (!HAS_CLERK) {
    return (
      <div className="max-w-3xl mx-auto px-6 py-24 text-center">
        <h1 className="font-display text-2xl text-fg mb-2">Simulation history</h1>
        <p className="text-sm text-fg-muted mb-6">
          Sign-in is not configured on this deployment, so per-user history is
          unavailable.
        </p>
        <Link href="/" className="text-sm text-glow underline decoration-glow/30 underline-offset-2">
          Back to simulations
        </Link>
      </div>
    );
  }

  const { userId } = await auth();
  if (!userId) return null;

  const simulations = await getHistory(userId);

  return (
    <div className="max-w-3xl mx-auto px-6 py-12">
      <h1 className="font-display text-2xl text-fg mb-8">Simulation history</h1>

      {simulations.length === 0 ? (
        <div className="text-center py-16 text-fg-faint">
          <p className="mb-4">No simulations yet.</p>
          <Link
            href="/"
            className="text-sm text-glow underline decoration-glow/30 underline-offset-2"
          >
            Run your first simulation
          </Link>
        </div>
      ) : (
        <div className="surface overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-ink-950/60 border-b border-ink-700">
              <tr>
                <th className="text-left px-4 py-3 eyebrow font-normal">
                  Event
                </th>
                <th className="text-left px-4 py-3 eyebrow font-normal">
                  Domain
                </th>
                <th className="text-left px-4 py-3 eyebrow font-normal">
                  Status
                </th>
                <th className="text-right px-4 py-3 eyebrow font-normal">
                  Cost
                </th>
                <th className="text-right px-4 py-3 eyebrow font-normal">
                  Date
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-ink-700">
              {simulations.map((sim) => (
                <tr key={sim.id} className="hover:bg-ink-800/50 transition-colors">
                  <td className="px-4 py-3">
                    <a
                      href={`/report/${sim.id}`}
                      className="text-fg hover:text-glow hover:underline underline-offset-2 line-clamp-1 transition-colors"
                    >
                      {sim.result_json?.seed_summary ?? sim.id.slice(0, 8) + "..."}
                    </a>
                  </td>
                  <td className="px-4 py-3 text-fg-muted">{sim.domain_id}</td>
                  <td className="px-4 py-3">{statusBadge(sim.status)}</td>
                  <td className="px-4 py-3 text-right text-fg-muted tabular-nums font-mono">
                    ${Number(sim.cost_usd).toFixed(4)}
                  </td>
                  <td className="px-4 py-3 text-right text-fg-faint tabular-nums text-xs font-mono">
                    {new Date(sim.created_at).toLocaleDateString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
