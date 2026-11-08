"use client";
import Link from "next/link";
import { useState } from "react";
import type { DailySummary } from "@/lib/types";
import { useApi } from "@/lib/api";
import { mg, time, todayKey } from "@/lib/format";
import DailyChart from "@/components/charts/DailyChart";
import MealTimeline from "@/components/charts/MealTimeline";
import { IconAlert, IconPlus } from "@/components/Icons";

type DayRow = { date: string; iron_mg: number; absorbed_mg: number };

export default function TodayPage() {
  const [date, setDate] = useState(todayKey());
  const { data: day, error } = useApi<DailySummary>(`/me/daily?date=${date}`);
  const { data: week } = useApi<DayRow[]>("/me/history?days=7");
  const isToday = date === todayKey();
  // Scale to the week's own max: against the 2.66 mg reference every bar would be a sliver.
  const weekMax = Math.max(...(week ?? []).map((d) => d.absorbed_mg), 0.01);

  return (
    <div className="space-y-5">
      <div className="flex items-end justify-between">
        <div>
          <div className="text-sm text-ink-2">{new Date(date + "T12:00").toLocaleDateString([], { weekday: "long", day: "numeric", month: "long" })}</div>
          <h1 className="text-2xl font-bold">{isToday ? "Today" : "Day view"}</h1>
        </div>
        <Link href="/log" className="btn btn-primary !min-h-10"><IconPlus className="w-5 h-5" />Log</Link>
      </div>

      {error && <p className="text-critical text-sm">{error.message}</p>}
      {!day && !error && <p className="text-muted animate-pulse">Loading…</p>}

      {day && (
        <>
          <DailyChart day={day} />
          {isToday && new Date().getHours() >= 17 && day.absorbed_mg < day.expected_absorbed_mg * 0.5 && (
            <div className="card p-3 text-sm flex gap-3" style={{ borderColor: "var(--warning)" }}>
              <IconAlert className="w-5 h-5 shrink-0" />
              You&apos;re low on absorbed iron today. A vitamin C rich side with dinner would help.
            </div>
          )}

          {day.meals.length > 0 ? (
            <>
              <div className="card p-3"><MealTimeline meals={day.meals.map((m) => ({ ...m }))} /></div>
              <section>
                <h2 className="font-semibold mb-2">Meals</h2>
                <ul className="space-y-2">
                  {day.meals.map((m) => (
                    <li key={m.id}>
                      <Link href={`/meal/${m.id}`} className="card p-3 flex items-center justify-between">
                        <div>
                          <div className="font-medium">{m.label} <span className="text-ink-2 font-normal text-sm">· {time(m.eaten_at)}</span></div>
                          <div className="text-xs text-ink-2 tabular">{mg(m.iron_mg, 1)} eaten → <strong className="text-ink">{mg(m.absorbed_mg)}</strong> absorbed</div>
                        </div>
                        {m.conflict_count > 0 && (
                          <span className="text-xs font-medium text-critical flex items-center gap-1"><IconAlert className="w-4 h-4" />{m.conflict_count} conflict{m.conflict_count > 1 ? "s" : ""}</span>
                        )}
                      </Link>
                    </li>
                  ))}
                </ul>
              </section>
            </>
          ) : (
            <div className="card p-6 text-center text-ink-2">
              No meals logged {isToday ? "yet today" : "this day"}.
              {isToday && <Link href="/log" className="block text-brand font-medium mt-2">Log your first meal</Link>}
            </div>
          )}
        </>
      )}

      {week && (
        <section className="card p-3">
          <h2 className="text-sm text-ink-2 mb-2">Absorbed iron, last 7 days (mg). Tap a day</h2>
          <div className="grid grid-cols-7 gap-1.5 items-end h-28">
            {week.map((d) => (
              <button key={d.date} onClick={() => setDate(d.date)} className="flex flex-col items-center justify-end h-full gap-1" aria-label={`${d.date}: ${d.absorbed_mg} mg absorbed`}>
                <span className="text-[10px] tabular text-ink-2">{d.absorbed_mg.toFixed(2)}</span>
                <span className="w-full rounded-t-[4px]" style={{ height: `${Math.max(3, (d.absorbed_mg / weekMax) * 70)}%`, background: "var(--series-1)", opacity: d.date === date ? 1 : 0.45 }} />
                <span className={`text-[11px] ${d.date === date ? "font-bold" : "text-ink-2"}`}>{new Date(d.date + "T12:00").toLocaleDateString([], { weekday: "narrow" })}</span>
              </button>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
