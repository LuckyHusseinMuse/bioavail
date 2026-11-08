"use client";
// Meal timeline: meals on a time axis with each meal's interaction window shaded.
// Drinks are dots; an inhibiting drink inside a window is flagged ("affects lunch"),
// outside the window it is marked clear. Shape + text label, not colour alone.
import { useState } from "react";
import type { Drink } from "@/lib/types";

export type TimelineMeal = { id: string; label: string; eaten_at: string; drinks: Drink[]; window_min: number };

const W = 360, H = 150, PAD_L = 12, PAD_R = 12, AXIS_Y = 118, MEAL_Y = 60;

export default function MealTimeline({ meals, startHour = 6, endHour = 23 }: { meals: TimelineMeal[]; startHour?: number; endHour?: number }) {
  const [focus, setFocus] = useState<string | null>(null);
  const minutes = (iso: string) => { const d = new Date(iso); return d.getHours() * 60 + d.getMinutes(); };
  const span = (endHour - startHour) * 60;
  const x = (min: number) => PAD_L + ((min - startHour * 60) / span) * (W - PAD_L - PAD_R);
  const fmt = (min: number) => `${String(Math.floor(min / 60) % 24).padStart(2, "0")}:${String(Math.round(min % 60)).padStart(2, "0")}`;

  const dots = meals.flatMap((m) =>
    m.drinks.map((d, i) => {
      const t = minutes(m.eaten_at) + d.offset_min;
      const inWindow = Math.abs(d.offset_min) < m.window_min;
      return { key: `${m.id}-${i}`, t, d, meal: m, inWindow, conflict: inWindow && !!d.inhibitor };
    }),
  );
  const focused = dots.find((d) => d.key === focus);
  const ticks: number[] = [];
  for (let h = startHour; h <= endHour; h += 3) ticks.push(h * 60);

  return (
    <figure>
      <figcaption className="text-sm text-ink-2 mb-1">Meals, drinks and the {meals[0]?.window_min ?? 60}-minute interaction window</figcaption>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto" role="img" aria-label="Meal timeline">
        {meals.map((m) => {
          const t = minutes(m.eaten_at);
          return (
            <g key={m.id}>
              <rect x={x(t - m.window_min)} y={22} width={x(t + m.window_min) - x(t - m.window_min)} height={AXIS_Y - 22} rx={8} fill="var(--series-1)" opacity={0.1} />
              <line x1={x(t)} x2={x(t)} y1={MEAL_Y} y2={AXIS_Y} stroke="var(--series-1)" strokeWidth={2} />
              <circle cx={x(t)} cy={MEAL_Y} r={7} fill="var(--series-1)" stroke="var(--surface)" strokeWidth={2} />
              <text x={x(t)} y={16} textAnchor="middle" fontSize={11} fontWeight={600} fill="var(--text)">{m.label}</text>
            </g>
          );
        })}
        <line x1={PAD_L} x2={W - PAD_R} y1={AXIS_Y} y2={AXIS_Y} stroke="var(--border)" />
        {ticks.map((t) => (
          <text key={t} x={x(t)} y={AXIS_Y + 16} textAnchor="middle" fontSize={10} fill="var(--text-2)">{fmt(t)}</text>
        ))}
        {dots.map((d) => (
          <g key={d.key} onClick={() => setFocus(d.key === focus ? null : d.key)} style={{ cursor: "pointer" }}>
            <circle cx={x(d.t)} cy={92} r={16} fill="transparent" />
            {d.conflict ? (
              <rect x={x(d.t) - 6} y={86} width={12} height={12} rx={2} fill="var(--critical)" stroke="var(--surface)" strokeWidth={2} transform={`rotate(45 ${x(d.t)} 92)`} />
            ) : (
              <circle cx={x(d.t)} cy={92} r={6} fill={d.d.inhibitor ? "var(--good)" : "var(--muted)"} stroke="var(--surface)" strokeWidth={2} />
            )}
            <title>{`${d.d.name} at ${fmt(d.t)}${d.conflict ? `, inside the ${d.meal.label.toLowerCase()} window` : ""}`}</title>
          </g>
        ))}
      </svg>
      <div className="min-h-10 text-sm">
        {focused ? (
          <p className={focused.conflict ? "text-critical" : "text-ink-2"}>
            <strong>{focused.d.name}</strong> at {fmt(focused.t)}:{" "}
            {focused.conflict
              ? `inside the ${focused.meal.label.toLowerCase()} window, so it reduces the iron you absorb from that meal.`
              : focused.d.inhibitor
                ? `outside the ${focused.meal.label.toLowerCase()} window, so no effect on that meal.`
                : "no known effect on iron."}
          </p>
        ) : (
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-2">
            <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rotate-45 bg-critical inline-block" />drink inside a meal window</span>
            <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-good inline-block" />inhibitor, outside window</span>
            <span>Tap a drink for details</span>
          </div>
        )}
      </div>
    </figure>
  );
}
