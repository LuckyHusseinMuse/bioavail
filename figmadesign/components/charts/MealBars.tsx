"use client";
// Home: eaten vs absorbed per meal. Same unit (mg) so one axis is honest. The tiny absorbed bars ARE the story.
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis } from "recharts";

export default function MealBars({ data }: { data: { label: string; eaten: number; absorbed: number }[] }) {
  return (
    <div>
      <div className="h-32">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} barGap={3} margin={{ top: 6, right: 0, left: 0, bottom: 0 }}>
            <XAxis dataKey="label" tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: "var(--muted)" }} />
            <Tooltip cursor={{ fill: "var(--surface-2)" }}
              contentStyle={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 12, fontSize: 12, color: "var(--text)" }}
              formatter={(v, n) => [`${Number(v).toFixed(2)} mg`, n === "eaten" ? "Eaten" : "Absorbed"]} />
            <Bar dataKey="eaten" fill="color-mix(in oklab, var(--primary) 28%, var(--surface-2))" radius={[4, 4, 0, 0]} maxBarSize={22} />
            <Bar dataKey="absorbed" fill="var(--primary)" radius={[4, 4, 0, 0]} maxBarSize={22} minPointSize={2} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div className="mt-1 flex gap-4 text-[11px] text-muted">
        <span className="flex items-center gap-1.5"><i className="h-2 w-2 rounded-sm" style={{ background: "color-mix(in oklab, var(--primary) 28%, var(--surface-2))" }} />Eaten</span>
        <span className="flex items-center gap-1.5"><i className="h-2 w-2 rounded-sm bg-primary" />Absorbed</span>
      </div>
    </div>
  );
}
