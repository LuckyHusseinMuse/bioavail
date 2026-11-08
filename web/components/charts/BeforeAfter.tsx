"use client";
// Before and after: absorbed mg for the current meal vs each fix suggestion.
// One series. "Now" is muted, suggestions are series-1, the selected one is fully opaque.
import { Bar, BarChart, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { FixSuggestion } from "@/lib/types";

export default function BeforeAfter({ before, suggestions, selectedId }: { before: number; suggestions: FixSuggestion[]; selectedId?: string | null }) {
  const rows = [
    { id: "now", name: "Now", mg: before },
    ...suggestions.map((s) => ({ id: s.id, name: s.title.length > 26 ? s.title.slice(0, 25) + "…" : s.title, mg: s.after_mg })),
  ];
  const fmt = (v: number) => `${v.toFixed(v < 1 ? 2 : 1)} mg`;
  return (
    <figure>
      <figcaption className="text-sm text-ink-2 mb-1">Iron absorbed from this meal, mg</figcaption>
      <div style={{ height: 40 + rows.length * 44 }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={rows} layout="vertical" margin={{ top: 4, right: 56, left: 0, bottom: 4 }} barCategoryGap={10}>
            <XAxis type="number" hide domain={[0, "dataMax"]} />
            <YAxis type="category" dataKey="name" width={150} tick={{ fontSize: 12, fill: "var(--text)" }} tickLine={false} axisLine={false} />
            <Tooltip
              cursor={{ fill: "var(--surface-2)" }}
              contentStyle={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 12, color: "var(--text)", fontSize: 12 }}
              formatter={(v) => [fmt(Number(v)), "Absorbed"]}
            />
            <Bar dataKey="mg" radius={[0, 4, 4, 0]} isAnimationActive>
              {rows.map((r) => (
                <Cell key={r.id} fill={r.id === "now" ? "var(--muted)" : "var(--series-1)"} fillOpacity={!selectedId || r.id === selectedId || r.id === "now" ? 1 : 0.45} />
              ))}
              <LabelList dataKey="mg" position="right" formatter={(v) => fmt(Number(v))} style={{ fontSize: 12, fill: "var(--text)", fontWeight: 600 }} />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </figure>
  );
}
