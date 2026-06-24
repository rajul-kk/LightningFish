"use client";
import { useEffect, useRef, useState } from "react";
import type { RoundEvent, SimulationCompleteEvent } from "./types";

interface SSEState {
  rounds: RoundEvent[];
  isComplete: boolean;
  error: string | null;
  totalCost: number;
}

export function useSimulationStream(simulationId: string | null): SSEState {
  const [state, setState] = useState<SSEState>({
    rounds: [],
    isComplete: false,
    error: null,
    totalCost: 0,
  });
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!simulationId) return;

    const pythonUrl =
      process.env.NEXT_PUBLIC_PYTHON_SERVICE_URL ?? "http://localhost:8000";
    const es = new EventSource(`${pythonUrl}/simulate/${simulationId}`);
    esRef.current = es;

    es.onmessage = (e) => {
      const data = JSON.parse(e.data as string);
      if (data.type === "complete") {
        const complete = data as SimulationCompleteEvent;
        setState((prev) => ({
          ...prev,
          isComplete: true,
          totalCost: complete.total_cost_usd,
        }));
        es.close();
      } else if (data.type === "error") {
        setState((prev) => ({ ...prev, error: data.message as string }));
        es.close();
      } else {
        const round = data as RoundEvent;
        setState((prev) => ({ ...prev, rounds: [...prev.rounds, round] }));
      }
    };

    es.onerror = () => {
      setState((prev) => ({
        ...prev,
        error: "Connection lost. Refresh to retry.",
      }));
      es.close();
    };

    return () => {
      es.close();
    };
  }, [simulationId]);

  return state;
}
