"use client";
import { useUser } from "@clerk/nextjs";
import { useState, useEffect } from "react";
import Link from "next/link";
import { HAS_CLERK } from "@/lib/clerk";

interface ApiKey {
  id: string;
  name: string;
  created_at: string;
  last_used_at: string | null;
}

const PY = process.env.NEXT_PUBLIC_PYTHON_SERVICE_URL ?? "http://localhost:8000";

/**
 * Auth is optional app-wide, so this page must not assume a <ClerkProvider>
 * exists. Calling useUser() without one throws at prerender and fails the
 * whole build — so the hook lives in the inner component, reached only when
 * Clerk is actually configured.
 */
export default function ApiKeysPage() {
  if (!HAS_CLERK) {
    return (
      <div className="max-w-xl mx-auto px-6 py-24 text-center">
        <h1 className="font-display text-2xl text-fg mb-2">API Keys</h1>
        <p className="text-sm text-fg-muted mb-6">
          Sign-in is not configured on this deployment, so API keys are
          unavailable. Set <code className="font-mono text-xs bg-ink-800 px-1.5 py-0.5 rounded">NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY</code>{" "}
          and <code className="font-mono text-xs bg-ink-800 px-1.5 py-0.5 rounded">CLERK_SECRET_KEY</code> to enable it.
        </p>
        <Link href="/" className="text-sm text-glow underline decoration-glow/30 underline-offset-2">
          Back to simulations
        </Link>
      </div>
    );
  }
  return <ApiKeysInner />;
}

function ApiKeysInner() {
  const { user } = useUser();
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [name, setName] = useState("");
  const [loading, setLoading] = useState(false);
  const [newKey, setNewKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!user?.id) return;
    fetch(`${PY}/keys?user_id=${user.id}`)
      .then((r) => r.json())
      .then(setKeys)
      .catch(() => {});
  }, [user?.id]);

  async function createKey() {
    if (!name.trim() || !user?.id) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${PY}/keys`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: user.id, name: name.trim() }),
      });
      if (!res.ok) throw new Error(await res.text());
      const data = (await res.json()) as { key: string; id: string; name: string };
      setNewKey(data.key);
      setName("");
      setKeys((prev) => [
        { id: data.id, name: data.name, created_at: new Date().toISOString(), last_used_at: null },
        ...prev,
      ]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create key");
    } finally {
      setLoading(false);
    }
  }

  async function deleteKey(id: string) {
    if (!user?.id) return;
    await fetch(`${PY}/keys/${id}?user_id=${user.id}`, { method: "DELETE" });
    setKeys((prev) => prev.filter((k) => k.id !== id));
  }

  return (
    <div className="max-w-xl mx-auto px-6 py-12">
      <h1 className="font-display text-2xl text-fg mb-2">API Keys</h1>
      <p className="text-sm text-fg-muted mb-8">
        Use API keys to access the Lightningfish simulation API from your own
        applications.
      </p>

      {newKey && (
        <div className="mb-6 border border-glow/30 bg-glow-dim rounded-xl p-4">
          <p className="text-xs font-medium text-glow mb-2">
            Key created — copy it now, it won&apos;t be shown again.
          </p>
          <code className="text-sm font-mono text-fg break-all">
            {newKey}
          </code>
          <button
            onClick={() => setNewKey(null)}
            className="mt-3 text-xs text-glow underline decoration-glow/30 underline-offset-2 block hover:text-glow-bright"
          >
            Dismiss
          </button>
        </div>
      )}

      <div className="surface p-5 mb-6">
        <h2 className="text-sm font-medium text-fg mb-3">Create new key</h2>
        <div className="flex gap-2">
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && createKey()}
            placeholder="Key name (e.g. production)"
            className="field flex-1 py-2"
          />
          <button
            onClick={createKey}
            disabled={loading || !name.trim()}
            className="btn-primary text-sm px-4 py-2"
          >
            {loading ? "Creating..." : "Create"}
          </button>
        </div>
        {error && <p className="text-xs text-coral mt-2">{error}</p>}
      </div>

      {keys.length > 0 && (
        <div className="surface overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-ink-950/60 border-b border-ink-700">
              <tr>
                <th className="text-left px-4 py-3 eyebrow font-normal">
                  Name
                </th>
                <th className="text-left px-4 py-3 eyebrow font-normal">
                  Created
                </th>
                <th className="text-left px-4 py-3 eyebrow font-normal">
                  Last used
                </th>
                <th />
              </tr>
            </thead>
            <tbody className="divide-y divide-ink-700">
              {keys.map((key) => (
                <tr key={key.id}>
                  <td className="px-4 py-3 font-medium text-fg">{key.name}</td>
                  <td className="px-4 py-3 text-fg-faint text-xs tabular-nums font-mono">
                    {new Date(key.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-3 text-fg-faint text-xs font-mono">
                    {key.last_used_at
                      ? new Date(key.last_used_at).toLocaleDateString()
                      : "Never"}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      onClick={() => deleteKey(key.id)}
                      className="text-xs text-coral/80 hover:text-coral transition-colors"
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {keys.length === 0 && (
        <p className="text-sm text-fg-faint text-center py-6">
          No API keys yet.
        </p>
      )}
    </div>
  );
}
