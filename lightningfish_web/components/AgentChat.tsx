"use client";
import { useState } from "react";
import { chatWithAgent } from "@/lib/api";

interface Message {
  role: "user" | "agent";
  text: string;
  archetype?: string;
}

interface Props {
  simulationId: string;
  domainId: string;
}

const FINANCE_ARCHETYPES = [
  "ValueInvestor",
  "MomentumTrader",
  "ShortSeller",
  "InstitutionalAnalyst",
  "RetailFOMO",
];

const CODING_ARCHETYPES = [
  "SecurityReviewer",
  "PerformanceReviewer",
  "DomainExpertMaintainer",
  "JuniorContributor",
  "StyleMaintainability",
];

export function AgentChat({ simulationId, domainId }: Props) {
  const archetypes =
    domainId === "finance" ? FINANCE_ARCHETYPES : CODING_ARCHETYPES;

  const [archetype, setArchetype] = useState(archetypes[0]);
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);

  async function send() {
    if (!input.trim()) return;
    const userMsg = input.trim();
    setInput("");
    setMessages((prev) => [...prev, { role: "user", text: userMsg }]);
    setLoading(true);
    try {
      const { reply } = await chatWithAgent(simulationId, archetype, userMsg);
      setMessages((prev) => [
        ...prev,
        { role: "agent", text: reply, archetype },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "agent", text: "Failed to get a response.", archetype },
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="surface overflow-hidden">
      <div className="border-b border-ink-700 px-4 py-3 flex items-center gap-3 bg-ink-950/40">
        <span className="text-xs font-medium text-fg-muted">Talk to:</span>
        <select
          value={archetype}
          onChange={(e) => setArchetype(e.target.value)}
          className="text-sm border-0 bg-transparent focus:outline-none font-medium text-glow"
        >
          {archetypes.map((a) => (
            <option key={a} value={a} className="bg-ink-900 text-fg">
              {a}
            </option>
          ))}
        </select>
      </div>

      <div className="min-h-48 max-h-80 overflow-y-auto p-4 space-y-3">
        {messages.length === 0 && (
          <p className="text-sm text-fg-faint text-center py-4">
            Ask an agent persona how they viewed this event.
          </p>
        )}
        {messages.map((msg, i) => (
          <div
            key={i}
            className={`text-sm ${msg.role === "user" ? "text-right" : "text-left"}`}
          >
            {msg.role === "agent" && msg.archetype && (
              <span className="text-xs text-fg-faint block mb-1">
                {msg.archetype}
              </span>
            )}
            <span
              className={`inline-block px-3 py-2 rounded-xl max-w-xs text-left ${
                msg.role === "user"
                  ? "bg-glow text-ink-950"
                  : "bg-ink-800 text-fg"
              }`}
            >
              {msg.text}
            </span>
          </div>
        ))}
        {loading && (
          <div className="text-sm text-fg-faint italic">Thinking...</div>
        )}
      </div>

      <div className="border-t border-ink-700 p-3 flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !loading && send()}
          placeholder="Ask this agent..."
          className="flex-1 text-sm border-0 focus:outline-none bg-transparent placeholder:text-fg-faint text-fg"
        />
        <button
          onClick={send}
          disabled={loading || !input.trim()}
          className="text-sm font-medium text-glow disabled:text-fg-faint transition-colors"
        >
          Send
        </button>
      </div>
    </div>
  );
}
