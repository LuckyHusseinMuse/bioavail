"use client";
// SCREEN 13: History. Day / Week / Month, % or mg, meal list with conflict dots, empty state.
import { CalendarX2, FlaskConical, Loader2 } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";
import { toast } from "sonner";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Button, Card, EmptyState, PageTitle, Segmented } from "@/components/ui/primitives";
import { isToday, resultOf, timeOf, useStore } from "@/lib/store";

type Range = "day" | "week" | "month";
// Local calendar day (not UTC), so late meals land on the right day.
const dayKey = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const mg = (n: number) => (n < 0.1 ? n.toFixed(3) : n < 1 ? n.toFixed(2) : n.toFixed(1));

export default function HistoryPage() {
  const meals = useStore((s) => s.meals);
  const setCurrent = useStore((s) => s.setCurrentMeal);
  const [range, setRange] = useState<Range>("week");
  const [unit, setUnit] = useState<"pct" | "mg">("pct");
  const removeDemo = useStore((s) => s.removeDemo);
  const [removing, setRemoving] = useState(false);
  const demoCount = meals.filter((m) => m.source === "seed").length;

  const scored = useMemo(() => meals.map((m) => ({ m, r: resultOf(m) })).sort((a, b) => b.m.eaten_at.localeCompare(a.m.eaten_at)), [meals]);

  const { points, list } = useMemo(() => {
    if (range === "day") {
      const today = scored.filter((x) => isToday(x.m.eaten_at)).reverse();
      return { points: today.map((x) => ({ x: timeOf(x.m.eaten_at), pct: x.r.fractional_pct, mg: x.r.absorbed_mg })), list: today.slice().reverse() };
    }
    const days = range === "week" ? 7 : 30;
    const pts = [];
    for (let i = days - 1; i >= 0; i--) {
      const d = new Date(); d.setDate(d.getDate() - i);
      const k = dayKey(d);
      const ms = scored.filter((x) => dayKey(new Date(x.m.eaten_at)) === k);
      const eaten = ms.reduce((t, x) => t + x.r.iron_mg, 0), abs = ms.reduce((t, x) => t + x.r.absorbed_mg, 0);
      pts.push({ x: d.toLocaleDateString("en-GB", range === "week" ? { weekday: "short" } : { day: "numeric" }),
        pct: ms.length && eaten ? +((abs / eaten) * 100).toFixed(2) : null, mg: ms.length ? +abs.toFixed(3) : null });
    }
    const since = Date.now() - days * 86400000;
    return { points: pts.some((p) => p.pct !== null) ? pts : [], list: scored.filter((x) => Date.parse(x.m.eaten_at) >= since) };
  }, [scored, range]);

  if (!meals.length) {
    return (
      <div className="space-y-4">
        <PageTitle eyebrow="Your meals" title="History" />
        <EmptyState icon={<CalendarX2 className="h-7 w-7" />} title="No meals logged yet" body="Your absorption over time will show here." action={<Button href="/add">Add a meal</Button>} />
      </div>
    );
  }

  const key = unit === "pct" ? "pct" : "mg";
  return (
    <div className="space-y-4">
      <PageTitle eyebrow="Your meals" title="History" />
      {demoCount > 0 && (
        <Card className="flex items-center gap-3 p-4">
          <FlaskConical className="h-5 w-5 shrink-0 text-amber" />
          <p className="flex-1 text-sm"><strong>{demoCount} demo meals</strong> <span className="text-muted">are mixed in. Remove them to see only what you logged.</span></p>
          <Button size="sm" variant="secondary" disabled={removing} onClick={async () => {
            setRemoving(true);
            try { await removeDemo(); toast.success("Demo meals removed"); } catch (e) { toast.error(`Couldn't remove them: ${e instanceof Error ? e.message : e}`); } finally { setRemoving(false); }
          }}>{removing ? <Loader2 className="h-4 w-4 animate-spin" /> : "Remove"}</Button>
        </Card>
      )}
      <Segmented id="range" value={range} onChange={setRange} options={[{ value: "day", label: "Day" }, { value: "week", label: "Week" }, { value: "month", label: "Month" }]} />
      <Card className="p-4">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-bold">Absorption {unit === "pct" ? "(% of iron eaten)" : "(mg absorbed)"}</h2>
          <Segmented id="unit" size="sm" className="w-28" value={unit} onChange={setUnit} options={[{ value: "pct", label: "%" }, { value: "mg", label: "mg" }]} />
        </div>
        <div className="mt-2 h-44">
          {points.length ? (
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={points} margin={{ top: 8, right: 14, left: -16, bottom: 0 }}>
                <defs>
                  <linearGradient id="hist" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="var(--primary)" stopOpacity={0.3} /><stop offset="100%" stopColor="var(--primary)" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid vertical={false} stroke="var(--grid)" />
                <XAxis dataKey="x" tickLine={false} axisLine={false} tick={{ fontSize: 10, fill: "var(--muted)" }} interval={range === "month" ? 4 : 0} />
                <YAxis tickLine={false} axisLine={false} tick={{ fontSize: 10, fill: "var(--muted)" }} tickCount={4} tickFormatter={(v: number) => (unit === "pct" ? `${+v.toFixed(1)}%` : `${+v.toFixed(2)}`)} />
                <Tooltip contentStyle={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 12, fontSize: 12, color: "var(--text)" }}
                  formatter={(v) => [unit === "pct" ? `${v}%` : `${v} mg`, "Absorbed"]} />
                <Area type="monotone" dataKey={key} stroke="var(--primary)" strokeWidth={2.5} fill="url(#hist)" dot={{ r: range === "month" ? 2 : 3, fill: "var(--primary)", strokeWidth: 0 }} activeDot={{ r: 5 }} connectNulls={false} animationDuration={700} />
              </AreaChart>
            </ResponsiveContainer>
          ) : <p className="grid h-full place-items-center text-sm text-muted">No meals in this range</p>}
        </div>
      </Card>

      <section>
        <h2 className="mb-2 font-bold">Meals</h2>
        {list.length ? (
          <Card className="divide-y divide-border">
            {list.slice(0, 40).map(({ m, r }) => (
              <Link key={m.id} href="/absorb" onClick={() => setCurrent(m.id)} className="flex min-h-16 items-center gap-3 px-4 py-3 hover:bg-surface-2">
                <div className="min-w-0 flex-1">
                  <p className="truncate font-semibold">{m.source === "seed" && <span className="mr-1.5 rounded-full bg-amber/15 px-1.5 py-0.5 align-middle text-[10px] font-bold uppercase text-amber">Demo</span>}{m.items.map((i) => i.name).join(", ")}{m.drinks.length ? `, ${m.drinks.map((d) => d.name.toLowerCase()).join(", ")}` : ""}</p>
                  <p className="text-xs text-muted tabular">{range !== "day" && `${new Date(m.eaten_at).toLocaleDateString("en-GB", { weekday: "short", day: "numeric" })} · `}{m.label} {timeOf(m.eaten_at)} · {r.iron_mg} mg eaten, {mg(r.absorbed_mg)} mg absorbed</p>
                </div>
                {r.conflicts.length > 0 && <span className="h-2.5 w-2.5 shrink-0 rounded-full bg-inhibitor" title="A conflict fired" aria-label="Conflict" />}
              </Link>
            ))}
          </Card>
        ) : (
          <EmptyState icon={<CalendarX2 className="h-7 w-7" />} title="No meals logged yet" body={range === "day" ? "Nothing logged today." : undefined} />
        )}
        <p className="mt-2 flex items-center gap-1.5 px-1 text-xs text-muted"><i className="h-2 w-2 rounded-full bg-inhibitor" />A conflict fired for this meal</p>
      </section>
    </div>
  );
}
