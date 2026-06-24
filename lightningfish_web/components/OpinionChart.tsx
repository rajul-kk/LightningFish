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
        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
        <XAxis
          dataKey="round"
          tick={{ fontSize: 11, fill: "#a3a3a3" }}
          tickLine={false}
          axisLine={false}
          label={{ value: "Round", position: "insideBottom", offset: -2, fontSize: 11, fill: "#a3a3a3" }}
        />
        <YAxis
          domain={[-1, 1]}
          tick={{ fontSize: 11, fill: "#a3a3a3" }}
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
            border: "1px solid #e5e5e5",
            borderRadius: 8,
            boxShadow: "none",
          }}
          formatter={(v: number) => [v.toFixed(3), "Mean opinion"]}
          labelFormatter={(l) => `Round ${l}`}
        />
        <ReferenceLine y={0} stroke="#d4d4d4" strokeDasharray="4 4" />
        <Line
          type="monotone"
          dataKey="opinion"
          stroke="#1a1a1a"
          strokeWidth={2}
          dot={false}
          activeDot={{ r: 4, fill: "#1a1a1a" }}
          isAnimationActive={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
