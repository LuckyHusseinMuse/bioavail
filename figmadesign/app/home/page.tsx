"use client";
// SCREEN 2: Home
import { AlarmClock, AlertTriangle, ArrowRight, Lightbulb } from "lucide-react";
import Link from "next/link";
import MealBars from "@/components/charts/MealBars";
import { Button, Card, Chip, IconBadge, NotMedical, Ring } from "@/components/ui/primitives";
import { isToday, resultOf, timeOf, useStore } from "@/lib/store";
import { refIron } from "@/lib/profile";

const fmt = (n: number) => (n < 0.1 ? n.toFixed(3) : n < 1 ? n.toFixed(2) : n.toFixed(1));

export default function HomePage() {
  const meals = useStore((s) => s.meals);
  const alerts = useStore((s) => s.alerts);
  const profile = useStore((s) => s.profile);
  const setCurrent = useStore((s) => s.setCurrentMeal);

  const today = meals.filter((m) => isToday(m.eaten_at)).sort((a, b) => a.eaten_at.localeCompare(b.eaten_at));
  const scored = today.map((m) => ({ m, r: resultOf(m) }));
  const eaten = scored.reduce((t, x) => t + x.r.iron_mg, 0);
  const absorbed = scored.reduce((t, x) => t + x.r.absorbed_mg, 0);
  const ref = refIron(profile);
  const last = scored.at(-1);
  const alert = alerts.find((a) => a.type === "conflict" && a.meal_id) ?? alerts[0];
  const hour = new Date().getHours();

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between pt-1">
        <div>
          <p className="text-sm text-muted">{new Date().toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long" })}</p>
          <h1 className="text-[26px] font-extrabold tracking-[-0.02em]">Good {hour < 12 ? "morning" : hour < 18 ? "afternoon" : "evening"}</h1>
        </div>
        <Link href="/you" className="grid h-11 w-11 place-items-center rounded-full bg-primary/12 text-lg font-bold text-primary">{profile.name[0]}</Link>
      </div>

      <Card className="p-5">
        <div className="flex items-start justify-between">
          <h2 className="font-bold">Today</h2>
          <NotMedical />
        </div>
        <p className="mt-2 flex items-baseline gap-2">
          <span className="text-[44px] font-extrabold leading-none tracking-[-0.03em] tabular">{eaten.toFixed(1)}</span>
          <span className="text-sm text-muted">mg iron eaten <span className="text-faint">of {ref} mg daily reference</span></span>
        </p>
        <div className="mt-3 h-2 overflow-hidden rounded-full bg-surface-2">
          <div className="h-full rounded-full bg-primary/40 transition-all duration-700" style={{ width: `${Math.min(100, (eaten / ref) * 100)}%` }} />
        </div>
        <div className="mt-4 flex items-center gap-3 rounded-xl bg-primary/8 p-3">
          <IconBadge tone="green" size={36}><span className="text-sm font-extrabold">Fe</span></IconBadge>
          <p className="flex-1 text-sm">
            <strong className="text-base tabular">{fmt(absorbed)} mg absorbed</strong>
            <span className="block text-muted">{eaten ? Math.round((absorbed / eaten) * 1000) / 10 : 0}% of what you ate</span>
          </p>
        </div>
        {scored.length > 0 && <div className="mt-4"><MealBars data={scored.map(({ m, r }) => ({ label: m.label, eaten: r.iron_mg, absorbed: r.absorbed_mg }))} /></div>}
      </Card>

      {last && (
        <Card className="p-5">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-[11px] font-bold uppercase tracking-[0.08em] text-faint">Last meal · {timeOf(last.m.eaten_at)}</p>
              <h2 className="mt-1 font-bold">{[...last.m.items.slice(0, 1), ...last.m.drinks.slice(0, 1)].map((x) => x.name.replace(/^Black /, "").toLowerCase()).join(" and ").replace(/^./, (c) => c.toUpperCase())}</h2>
            </div>
          </div>
          <div className="mt-3 flex items-center gap-4">
            <Ring value={last.r.fractional_pct} max={15} color={last.r.conflicts.length ? "var(--inhibitor)" : "var(--primary)"}>
              <span className="text-lg font-extrabold leading-none tabular">{last.r.fractional_pct}%</span>
              <span className="block text-[10px] text-muted">absorbed</span>
            </Ring>
            <div className="space-y-2">
              <p className="text-sm"><strong className="tabular">{fmt(last.r.absorbed_mg)} mg</strong> <span className="text-muted">of {last.r.iron_mg} mg iron</span></p>
              {last.r.conflicts.length > 0 && <Chip tone="red" icon={<AlertTriangle className="h-3.5 w-3.5" />}>Tea reduces absorption</Chip>}
            </div>
          </div>
          <Link href="/absorb" onClick={() => setCurrent(last.m.id)} className="mt-3 flex min-h-11 items-center justify-between border-t border-border pt-3 text-sm font-bold text-primary">
            See the breakdown <ArrowRight className="h-4 w-4" />
          </Link>
        </Card>
      )}

      {alert && (
        <Card className="flex gap-3 p-4">
          <IconBadge tone={alert.type === "conflict" ? "red" : "amber"}><AlertTriangle className="h-5 w-5" /></IconBadge>
          <div className="flex-1">
            <p className="text-[11px] font-bold uppercase tracking-[0.08em] text-faint">Latest alert</p>
            <p className="mt-0.5 text-sm font-semibold">{alert.title}</p>
            {alert.meal_id && (
              <Link href="/fix" onClick={() => setCurrent(alert.meal_id!)} className="mt-1 inline-flex min-h-9 items-center gap-1 text-sm font-bold text-primary">
                Fix this meal <ArrowRight className="h-4 w-4" />
              </Link>
            )}
          </div>
        </Card>
      )}

      <Card className="flex items-center gap-3 p-4">
        <IconBadge tone="blue"><AlarmClock className="h-5 w-5" /></IconBadge>
        <div className="flex-1">
          <p className="font-bold">Set a reminder</p>
          <p className="text-sm text-muted">For a drink, or a supplement time.</p>
        </div>
        <Button href="/reminder" size="sm" variant="secondary">Create reminder</Button>
      </Card>

      <div className="flex gap-3 rounded-2xl bg-amber/12 p-4">
        <Lightbulb className="h-5 w-5 shrink-0 text-amber" />
        <p className="text-sm"><strong>Quick tip.</strong> Waiting an hour or two before tea can help you absorb more iron.</p>
      </div>
    </div>
  );
}
