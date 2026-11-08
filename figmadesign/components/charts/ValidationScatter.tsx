"use client";
// SCREEN 8: predicted vs measured absorption with a diagonal identity line.
import { CartesianGrid, ReferenceLine, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis } from "recharts";

type Row = { meal: string; study: string; measured: number; predicted: number };

export default function ValidationScatter({ rows }: { rows: Row[] }) {
  const max = Math.ceil(Math.max(...rows.flatMap((r) => [r.measured, r.predicted])) * 1.1);
  return (
    <div className="h-64">
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart margin={{ top: 8, right: 8, left: -18, bottom: 16 }}>
          <CartesianGrid stroke="var(--grid)" />
          <XAxis type="number" dataKey="measured" domain={[0, max]} unit="%" tick={{ fontSize: 11, fill: "var(--muted)" }} tickLine={false}
            label={{ value: "Measured in study", position: "insideBottom", offset: -8, fontSize: 11, fill: "var(--muted)" }} />
          <YAxis type="number" dataKey="predicted" domain={[0, max]} unit="%" tick={{ fontSize: 11, fill: "var(--muted)" }} tickLine={false} />
          <ReferenceLine segment={[{ x: 0, y: 0 }, { x: max, y: max }]} stroke="var(--faint)" strokeWidth={1}
            label={{ value: "perfect prediction", position: "insideTopLeft", fontSize: 10, fill: "var(--muted)" }} />
          <Tooltip cursor={false} content={({ payload }) => {
            const r = payload?.[0]?.payload as Row | undefined;
            return r ? (
              <div className="rounded-xl border border-border bg-surface p-2 text-xs shadow-card">
                <p className="font-bold">{r.meal}</p><p className="text-muted">{r.study}</p>
                <p className="mt-1 tabular">Measured {r.measured}% · Avail {r.predicted}%</p>
              </div>
            ) : null;
          }} />
          <Scatter data={rows} fill="var(--primary)" stroke="var(--surface)" strokeWidth={2} />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}
