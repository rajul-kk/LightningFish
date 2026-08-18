"use client";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
} from "recharts";

interface Props {
  trajectory: number[];
  negativePole: string;
  positivePole: string;
}

export function OpinionChart({ trajectory, negativePole, positivePole }: Props) {
  const data = trajectory.map((v, i) => ({ round: i + 1, opinion: v }));

  return (
    <ResponsiveContainer width="100%" height={220}>
      <LineChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1b2731" />
        <XAxis
          dataKey="round"
          tick={{ fontSize: 11, fill: "#546a6b" }}
          tickLine={false}
          axisLine={false}
          label={{ value: "Round", position: "insideBottom", offset: -2, fontSize: 11, fill: "#546a6b" }}
        />
        <YAxis
          domain={[-1, 1]}
          tick={{ fontSize: 11, fill: "#546a6b" }}
          tickLine={false}
          axisLine={false}
          tickFormatter={(v: number) =>
            v === 1 ? positivePole : v === -1 ? negativePole : v.toFixed(1)
          }
          width={56}
        />
        <Tooltip
          contentStyle={{
            fontSize: 12,
            background: "#0a0f14",
            border: "1px solid #1b2731",
            borderRadius: 8,
            boxShadow: "0 4px 16px rgba(0,0,0,0.4)",
            color: "#eaf3f0",
          }}
          labelStyle={{ color: "#8fa8a6" }}
          formatter={(v: number) => [v.toFixed(3), "Mean opinion"]}
          labelFormatter={(l) => `Round ${l}`}
        />
        <ReferenceLine y={0} stroke="#2a3941" strokeDasharray="4 4" />
        <Line
          type="monotone"
          dataKey="opinion"
          stroke="#3febb8"
          strokeWidth={2}
          dot={false}
          activeDot={{ r: 4, fill: "#3febb8", stroke: "#05070a", strokeWidth: 2 }}
          isAnimationActive={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
