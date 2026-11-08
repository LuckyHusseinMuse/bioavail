"use client";
// Absorption waterfall: base non-haem % → one bar per factor → final %.
// Floating bars = a transparent "offset" stack under a visible "delta" stack.
import { Bar, BarChart, CartesianGrid, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { EngineResult } from "@/lib/types";
import { FACTOR_LABEL } from "@/lib/format";

type Row = { name: string; offset: number; delta: number; from: number; to: number; tag: string; kind: "total" | "up" | "down" };

export function waterfallRows(r: EngineResult): Row[] {
  const rows: Row[] = [];
  let cur = r.base_pct;
  rows.push({ name: "Base", offset: 0, delta: cur, from: 0, to: cur, tag: `${cur}%`, kind: "total" });
  for (const c of r.contributions) {
    if (c.multiplier === 1) continue; // enhancers are already inside the Monsen base
    const next = cur * c.multiplier;
    rows.push({
      name: (FACTOR_LABEL[c.factor] ?? c.factor).split(" (")[0],
      offset: Math.min(cur, next), delta: Math.abs(next - cur), from: cur, to: next,
      tag: `×${c.multiplier}`, kind: next < cur ? "down" : "up",
    });
    cur = next;
  }
  rows.push({ name: "Final", offset: 0, delta: cur, from: 0, to: cur, tag: `${cur.toFixed(2)}%`, kind: "total" });
  return rows;
}

const COLOR = { total: "var(--series-1)", up: "var(--good)", down: "var(--critical)" };

export default function Waterfall({ result }: { result: EngineResult }) {
  const rows = waterfallRows(result);
  const enhancers = result.contributions.filter((c) => c.multiplier === 1 && (c.factor === "vitamin_c" || c.factor === "mfp"));
  return (
    <figure>
      <figcaption className="text-sm text-ink-2 mb-2">
        Non-haem iron absorption, % · base set by {enhancers.length ? enhancers.map((c) => `${c.amount ?? ""} ${c.unit ?? ""} ${(FACTOR_LABEL[c.factor] ?? c.factor).toLowerCase()}`).join(" + ") : "no enhancers"} (Monsen 1978)
      </figcaption>
      <div className="h-60">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={rows} margin={{ top: 22, right: 8, left: -18, bottom: 0 }} barCategoryGap="22%">
            <CartesianGrid vertical={false} stroke="var(--grid)" />
            <XAxis dataKey="name" tick={{ fontSize: 11, fill: "var(--text-2)" }} tickLine={false} axisLine={{ stroke: "var(--border)" }} interval={0} />
            <YAxis tick={{ fontSize: 11, fill: "var(--text-2)" }} tickLine={false} axisLine={false} unit="%" />
            <Tooltip
              cursor={{ fill: "var(--surface-2)" }}
              contentStyle={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 12, color: "var(--text)", fontSize: 12 }}
              formatter={(_v, _n, p) => {
                const d = (p as { payload: Row }).payload;
                return d.kind === "total" ? [`${d.to.toFixed(2)}%`, d.name] : [`${d.from.toFixed(2)}% → ${d.to.toFixed(2)}% (${d.tag})`, d.name];
              }}
            />
            <Bar dataKey="offset" stackId="w" fill="transparent" isAnimationActive={false} />
            <Bar dataKey="delta" stackId="w" radius={[4, 4, 4, 4]}>
              {rows.map((r, i) => <Cell key={i} fill={COLOR[r.kind]} />)}
              <LabelList dataKey="tag" position="top" style={{ fontSize: 11, fill: "var(--text)", fontWeight: 600 }} />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </figure>
  );
}
