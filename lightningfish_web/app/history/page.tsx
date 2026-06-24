import { auth } from "@clerk/nextjs/server";

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
    return (
      <span className="text-xs font-medium text-emerald-600 bg-emerald-50 border border-emerald-100 px-2 py-0.5 rounded-full">
        complete
      </span>
    );
  }
  if (status === "running") {
    return (
      <span className="text-xs font-medium text-blue-600 bg-blue-50 border border-blue-100 px-2 py-0.5 rounded-full">
        running
      </span>
    );
  }
  return (
    <span className="text-xs font-medium text-neutral-400 bg-neutral-50 border border-neutral-100 px-2 py-0.5 rounded-full">
      {status}
    </span>
  );
}

export default async function HistoryPage() {
  const { userId } = await auth();
  if (!userId) return null;

  const simulations = await getHistory(userId);

  return (
    <div className="max-w-3xl mx-auto px-6 py-12">
      <h1 className="text-2xl font-semibold mb-8">Simulation history</h1>

      {simulations.length === 0 ? (
        <div className="text-center py-16 text-neutral-400">
          <p className="mb-4">No simulations yet.</p>
          <a
            href="/"
            className="text-sm text-neutral-700 underline underline-offset-2"
          >
            Run your first simulation
          </a>
        </div>
      ) : (
        <div className="border border-neutral-200 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-neutral-50 border-b border-neutral-200">
              <tr>
                <th className="text-left px-4 py-3 text-xs font-medium text-neutral-400 uppercase tracking-wider">
                  Event
                </th>
                <th className="text-left px-4 py-3 text-xs font-medium text-neutral-400 uppercase tracking-wider">
                  Domain
                </th>
                <th className="text-left px-4 py-3 text-xs font-medium text-neutral-400 uppercase tracking-wider">
                  Status
                </th>
                <th className="text-right px-4 py-3 text-xs font-medium text-neutral-400 uppercase tracking-wider">
                  Cost
                </th>
                <th className="text-right px-4 py-3 text-xs font-medium text-neutral-400 uppercase tracking-wider">
                  Date
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-100">
              {simulations.map((sim) => (
                <tr key={sim.id} className="hover:bg-neutral-50 transition-colors">
                  <td className="px-4 py-3">
                    <a
                      href={`/report/${sim.id}`}
                      className="text-neutral-900 hover:underline underline-offset-2 line-clamp-1"
                    >
                      {sim.result_json?.seed_summary ?? sim.id.slice(0, 8) + "..."}
                    </a>
                  </td>
                  <td className="px-4 py-3 text-neutral-500">{sim.domain_id}</td>
                  <td className="px-4 py-3">{statusBadge(sim.status)}</td>
                  <td className="px-4 py-3 text-right text-neutral-500 tabular-nums">
                    ${Number(sim.cost_usd).toFixed(4)}
                  </td>
                  <td className="px-4 py-3 text-right text-neutral-400 tabular-nums text-xs">
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
