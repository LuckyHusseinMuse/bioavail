"use client";
// Daily eaten vs absorbed. Eaten and absorbed differ ~10x in scale, so they are NOT
// on one axis: two meters (each against its own reference) + a cumulative absorbed line.
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { DailySummary } from "@/lib/types";

function Meter({ label, value, target, unit = "mg", sub }: { label: string; value: number; target: number; unit?: string; sub: string }) {
  const p = Math.min(100, (value / target) * 100);
  return (
    <div className="card p-3">
      <div className="text-xs text-ink-2">{label}</div>
      <div className="text-2xl font-bold tabular mt-0.5">
        {value.toFixed(value < 1 ? 2 : 1)}<span className="text-sm font-medium text-ink-2"> / {target.toFixed(target < 3 ? 2 : 1)} {unit}</span>
      </div>
      <div className="h-2 rounded-full bg-surface-2 mt-2 overflow-hidden" role="meter" aria-valuenow={value} aria-valuemax={target} aria-label={label}>
        <div className="h-full rounded-full" style={{ width: `${p}%`, background: "var(--series-1)" }} />
      </div>
      <div className="text-[11px] text-muted mt-1.5">{sub}</div>
    </div>
  );
}

export default function DailyChart({ day }: { day: DailySummary }) {
  let cum = 0;
  const points = [{ t: "00:00", mg: 0, meal: "Start of day" }];
  for (const m of day.meals) {
    cum += m.absorbed_mg;
    const d = new Date(m.eaten_at);
    points.push({ t: d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }), mg: +cum.toFixed(3), meal: m.label });
  }
  const top = Math.max(day.expected_absorbed_mg, cum) * 1.15;

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3">
        <Meter label="Iron eaten" value={day.iron_mg} target={day.reference_iron_mg} sub="vs UK reference intake" />
        <Meter label="Iron absorbed" value={day.absorbed_mg} target={day.expected_absorbed_mg} sub="vs typical absorbed amount (EFSA)" />
      </div>
      <figure className="card p-3">
        <figcaption className="text-sm text-ink-2 mb-1">Absorbed iron so far today, mg (cumulative)</figcaption>
        <div className="h-44">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={points} margin={{ top: 12, right: 12, left: -20, bottom: 0 }}>
              <CartesianGrid vertical={false} stroke="var(--grid)" />
              <XAxis dataKey="t" tick={{ fontSize: 11, fill: "var(--text-2)" }} tickLine={false} axisLine={{ stroke: "var(--border)" }} />
              <YAxis domain={[0, +top.toFixed(2)]} tick={{ fontSize: 11, fill: "var(--text-2)" }} tickLine={false} axisLine={false} />
              <ReferenceLine y={day.expected_absorbed_mg} stroke="var(--text-2)" strokeWidth={1}
                label={{ value: `typical day ${day.expected_absorbed_mg} mg`, position: "insideTopRight", fontSize: 10, fill: "var(--text-2)" }} />
              <Tooltip
                contentStyle={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 12, color: "var(--text)", fontSize: 12 }}
                formatter={(v) => [`${Number(v).toFixed(2)} mg`, "Absorbed so far"]}
                labelFormatter={(l, p) => `${p?.[0]?.payload?.meal ?? ""} · ${l}`}
              />
              <Line type="stepAfter" dataKey="mg" stroke="var(--series-1)" strokeWidth={2} dot={{ r: 4, fill: "var(--series-1)", stroke: "var(--surface)", strokeWidth: 2 }} activeDot={{ r: 6 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </figure>
    </div>
  );
}
