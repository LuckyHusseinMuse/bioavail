"use client";
// Validation scatter: engine prediction vs measured absorption, one point per study meal,
// with the identity line (points on the line = perfect prediction). Table view below.
import { CartesianGrid, ReferenceLine, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis } from "recharts";
import type { ValidationReport, ValidationRow } from "@/lib/types";

export default function ValidationScatter({ report }: { report: ValidationReport }) {
  const max = Math.ceil(Math.max(...report.rows.flatMap((r) => [r.measured_pct, r.predicted_pct]), 1) * 1.1);
  return (
    <figure>
      <figcaption className="text-sm text-ink-2 mb-1">Predicted vs measured non-haem absorption, % (group means)</figcaption>
      <div className="h-72">
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart margin={{ top: 10, right: 12, left: -14, bottom: 18 }}>
            <CartesianGrid stroke="var(--grid)" />
            <XAxis type="number" dataKey="measured_pct" domain={[0, max]} name="Measured" unit="%" tick={{ fontSize: 11, fill: "var(--text-2)" }}
              label={{ value: "Measured in study", position: "insideBottom", offset: -10, fontSize: 11, fill: "var(--text-2)" }} />
            <YAxis type="number" dataKey="predicted_pct" domain={[0, max]} name="Predicted" unit="%" tick={{ fontSize: 11, fill: "var(--text-2)" }} />
            <ReferenceLine segment={[{ x: 0, y: 0 }, { x: max, y: max }]} stroke="var(--text-2)" strokeWidth={1}
              label={{ value: "perfect prediction", position: "insideTopLeft", fontSize: 10, fill: "var(--text-2)" }} ifOverflow="extendDomain" />
            <Tooltip
              cursor={{ strokeDasharray: "0" }}
              content={({ payload }) => {
                const r = payload?.[0]?.payload as ValidationRow | undefined;
                if (!r) return null;
                return (
                  <div className="card p-2 text-xs shadow">
                    <div className="font-semibold">{r.meal}</div>
                    <div className="text-ink-2">{r.study} · {r.measurement}</div>
                    <div className="tabular mt-1">Measured {r.measured_pct}% · Predicted {r.predicted_pct}%</div>
                  </div>
                );
              }}
            />
            <Scatter data={report.rows} fill="var(--series-1)" stroke="var(--surface)" strokeWidth={2} />
          </ScatterChart>
        </ResponsiveContainer>
      </div>
      <details className="mt-2 text-sm">
        <summary className="cursor-pointer text-brand font-medium">Show as table</summary>
        <div className="overflow-x-auto">
          <table className="w-full text-left mt-2 tabular">
            <thead className="text-ink-2 text-xs"><tr><th className="py-1">Meal</th><th>Study</th><th className="text-right">Measured</th><th className="text-right">Predicted</th></tr></thead>
            <tbody>
              {report.rows.map((r) => (
                <tr key={r.id} className="border-t border-border"><td className="py-1.5 pr-2">{r.meal}</td><td className="pr-2 text-ink-2">{r.study}</td><td className="text-right">{r.measured_pct}%</td><td className="text-right">{r.predicted_pct}%</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </figure>
  );
}
