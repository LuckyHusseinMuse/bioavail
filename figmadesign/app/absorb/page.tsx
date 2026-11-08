"use client";
// SCREEN 6: Absorb (Breakdown) · SCREEN 7: Map · SCREEN 8: Evidence · SCREEN 9: Evidence sheet · SCREEN 11: Conflict toast
import { AlertTriangle, ArrowRight, ArrowUpRight, ChevronDown, Info, Utensils } from "lucide-react";
import { animate, AnimatePresence, motion, useMotionValue, useTransform } from "motion/react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import EvidenceSheet from "@/components/EvidenceSheet";
import { Sheet } from "@/components/shell";
import InteractionMap from "@/components/charts/InteractionMap";
import ValidationScatter from "@/components/charts/ValidationScatter";
import Waterfall from "@/components/charts/Waterfall";
import { Button, Card, Chip, EmptyState, NotMedical, Segmented, cn } from "@/components/ui/primitives";
import { EVIDENCE, VALIDATION } from "@/lib/engine/evidence";
import { findFood } from "@/lib/engine/foods";
import type { EngineResult } from "@/lib/engine/types";
import { reductionPct } from "@/lib/logic";
import { conflictTitle, resultOf, timeOf, useStore, type Meal } from "@/lib/store";

function CountUp({ value, decimals = 1 }: { value: number; decimals?: number }) {
  const mv = useMotionValue(0);
  const text = useTransform(mv, (v) => v.toFixed(decimals));
  useEffect(() => { const c = animate(mv, value, { duration: 1, ease: [0.2, 0.8, 0.2, 1] }); return () => c.stop(); }, [mv, value]);
  return <motion.span className="tabular">{text}</motion.span>;
}

const mg = (n: number) => (n < 0.1 ? n.toFixed(3) : n < 1 ? n.toFixed(2) : n.toFixed(1));

function whyLines(meal: Meal, r: EngineResult): { lines: string[]; evidence: string } {
  const sources = meal.items.map((i) => ({ name: i.name, iron: ((findFood(i.food_code)?.iron_mg ?? 0) * i.grams) / 100, mfp: !!findFood(i.food_code)?.is_mfp }))
    .sort((a, b) => b.iron - a.iron);
  const top = sources[0];
  const first = top ? `Most of this meal's iron came from ${top.name.toLowerCase()}, so it was ${top.mfp ? "partly haem, the easier kind to absorb" : "non-haem"}.` : "";
  const worst = r.contributions.filter((c) => c.multiplier < 1 && c.factor !== "floor").sort((a, b) => a.multiplier - b.multiplier)[0];
  const second = !worst ? "Nothing in this meal strongly blocked absorption."
    : worst.factor === "polyphenols" ? "Tea polyphenols bound to that iron, leaving less available to absorb."
    : worst.factor === "phytate" ? "Phytate in the grains and legumes bound some of that iron."
    : "Calcium in the meal reduced how much iron was taken up.";
  return { lines: [first, second].filter(Boolean), evidence: worst?.factor === "polyphenols" ? "EVID_LINK_IRON_010" : worst?.factor === "phytate" ? "EVID_LINK_IRON_030" : worst?.factor === "calcium" ? "EVID_LINK_IRON_020" : "ABS_BASE_MONSEN" };
}

function AbsorbInner() {
  const router = useRouter();
  const params = useSearchParams();
  const meals = useStore((s) => s.meals);
  const currentId = useStore((s) => s.currentMealId);
  const setCurrent = useStore((s) => s.setCurrentMeal);
  const addAlertSeen = useRef(false);
  const q = params.get("tab");
  const [tab, setTab] = useState<"breakdown" | "map" | "evidence">(q === "map" || q === "evidence" ? q : "breakdown");
  const [evidence, setEvidence] = useState<string | null>(null);
  const [picker, setPicker] = useState(false);

  const meal = meals.find((m) => m.id === currentId) ?? meals.at(-1);
  const r = useMemo(() => (meal ? resultOf(meal) : null), [meal]);

  // SCREEN 11: conflict toast slides in from the top right after a meal is scored.
  useEffect(() => {
    if (!meal || !r || addAlertSeen.current) return;
    if (params.get("new") === "1" || params.get("toast") === "1") {
      addAlertSeen.current = true;
      if (r.conflicts.length) {
        setTimeout(() => toast(conflictTitle(meal) + ".", {
          icon: <AlertTriangle className="h-5 w-5 text-inhibitor" />, duration: 7000,
          action: { label: "See fix", onClick: () => router.push("/fix") },
        }), 700);
      }
    }
  }, [meal, r, params, router]);

  if (!meal || !r) {
    return <EmptyState icon={<Utensils className="h-7 w-7" />} title="No meals logged yet" body="Log a meal to see how much iron you absorb." action={<Button href="/add">Add a meal</Button>} />;
  }

  const haemAbs = r.haem_mg * 0.23;
  const nonAbs = Math.max(0, r.absorbed_mg - haemAbs);
  const why = whyLines(meal, r);
  const recent = [...meals].sort((a, b) => b.eaten_at.localeCompare(a.eaten_at)).slice(0, 8);

  return (
    <div className="space-y-4">
      <button onClick={() => setPicker(true)} className="inline-flex min-h-10 items-center gap-1.5 rounded-full border border-border bg-surface px-3.5 text-sm font-semibold">
        {meal.label}, {timeOf(meal.eaten_at)}<ChevronDown className="h-4 w-4 text-muted" />
      </button>

      {/* Hero */}
      <section className="relative overflow-hidden rounded-[22px] bg-gradient-to-br from-[color-mix(in_oklab,var(--primary)_80%,#000)] to-[color-mix(in_oklab,var(--primary)_48%,#000)] p-5 text-white">
        <div className="pointer-events-none absolute -right-10 -top-10 h-40 w-40 rounded-full bg-white/10 blur-2xl" />
        <p className="text-sm text-white/85">Ate <strong className="text-white">{r.iron_mg} mg</strong>, absorbed <strong className="text-white">{mg(r.absorbed_mg)} mg</strong></p>
        <p className="mt-2 flex items-baseline gap-2">
          <span className="text-[56px] font-extrabold leading-none tracking-[-0.04em]"><CountUp value={r.fractional_pct} decimals={r.fractional_pct < 1 ? 2 : 1} />%</span>
          <span className="text-lg font-semibold text-white/85">absorbed</span>
        </p>
        <p className="mt-1 flex items-center justify-between text-xs text-white/75"><span>range {r.range_pct[0]} to {r.range_pct[1]}%</span><span>Not medical advice</span></p>
        <div className="mt-4 flex h-2.5 overflow-hidden rounded-full bg-white/15">
          <motion.span className="bg-amber" initial={{ width: 0 }} animate={{ width: `${r.absorbed_mg ? (haemAbs / r.absorbed_mg) * 100 : 0}%` }} transition={{ duration: 0.8 }} />
          <motion.span className="bg-white/85" initial={{ width: 0 }} animate={{ width: `${r.absorbed_mg ? (nonAbs / r.absorbed_mg) * 100 : 0}%` }} transition={{ duration: 0.8, delay: 0.1 }} />
        </div>
        <div className="mt-2 flex gap-4 text-xs text-white/85">
          <span className="flex items-center gap-1.5"><i className="h-2 w-2 rounded-full bg-amber" />Haem <strong className="text-white tabular">{mg(haemAbs)} mg</strong></span>
          <span className="flex items-center gap-1.5"><i className="h-2 w-2 rounded-full bg-white/85" />Non-haem <strong className="text-white tabular">{mg(nonAbs)} mg</strong></span>
        </div>
      </section>

      <Segmented id="absorb" value={tab} onChange={setTab} options={[{ value: "breakdown", label: "Breakdown" }, { value: "map", label: "Map" }, { value: "evidence", label: "Evidence" }]} />

      <AnimatePresence mode="wait">
        <motion.div key={tab} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.2 }} className="space-y-4">
          {tab === "breakdown" && (
            <>
              {r.conflicts.map((c) => (
                <div key={c.rule_id} className="flex gap-3 rounded-2xl bg-inhibitor/10 p-4">
                  <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-inhibitor text-white"><AlertTriangle className="h-4 w-4" /></span>
                  <div className="text-sm">
                    <p className="font-semibold">{c.rule_id === "RULE_IRON_010" ? <><strong>{meal.drinks.find((d) => d.food_code === c.trigger)?.name ?? "Tea"} with this meal</strong> cuts non-haem iron absorption</> : c.message}</p>
                    <button onClick={() => setEvidence(c.evidence_id)} className="mt-1 inline-flex min-h-8 items-center gap-1 text-[13px] font-bold text-inhibitor">See source <ArrowUpRight className="h-3.5 w-3.5" /></button>
                  </div>
                </div>
              ))}
              {!!r.data_gaps?.length && (
                <div className="flex gap-2 rounded-xl bg-surface-2 p-3 text-sm text-muted"><Info className="mt-0.5 h-4 w-4 shrink-0" />Inhibitor data not available for {r.data_gaps.map((c) => findFood(c)?.name.toLowerCase()).join(", ")}. This estimate may be high.</div>
              )}
              <Card className="p-5">
                <h2 className="font-bold">Why this happened</h2>
                <div className="mt-2 space-y-1.5 text-sm text-muted">{why.lines.map((l) => <p key={l}>{l}</p>)}</div>
                <button onClick={() => setEvidence(why.evidence)} className="mt-3"><Chip tone="green" className="min-h-8">{EVIDENCE[why.evidence]?.short} <ArrowUpRight className="h-3.5 w-3.5" /></Chip></button>
              </Card>
              <Card className="p-5">
                <p className="text-[11px] font-bold uppercase tracking-[0.08em] text-faint">From food to you</p>
                <div className="mb-4 mt-0.5 flex items-baseline justify-between"><h2 className="font-bold">What changed your absorption</h2><NotMedical /></div>
                <Waterfall result={r} />
              </Card>
            </>
          )}
          {tab === "map" && <InteractionMap result={r} onEvidence={setEvidence} />}
          {tab === "evidence" && (
            <>
              <Card className="p-5">
                <h2 className="font-bold">Predicted vs measured absorption</h2>
                <p className="mb-2 text-xs text-muted">Each dot is a meal from a published study (mock rows for now).</p>
                <ValidationScatter rows={VALIDATION.rows} />
                <div className="mt-2 flex items-center justify-between rounded-xl bg-surface-2 p-3">
                  <span className="text-sm text-muted">Mean error</span>
                  <strong className="tabular">{VALIDATION.mae_pp} percentage points</strong>
                </div>
              </Card>
              <Card className="p-5">
                <h2 className="mb-2 font-bold">Relative effects</h2>
                <ul className="divide-y divide-border">
                  {VALIDATION.relative.map((x) => (
                    <li key={x.label} className="py-2.5 text-sm">
                      <span className="font-semibold">{x.label}:</span> Avail <strong className="text-primary tabular">{reductionPct(x.food_code)}%</strong>, {x.published}
                    </li>
                  ))}
                </ul>
              </Card>
              <p className="px-1 text-xs text-faint">Compared with published group means, not individuals.</p>
            </>
          )}
        </motion.div>
      </AnimatePresence>

      {tab !== "evidence" && (
        <div className="sticky-cta">
          <Button size="lg" href="/fix" className="w-full">Fix this meal <ArrowRight className="h-5 w-5" /></Button>
        </div>
      )}

      <EvidenceSheet id={evidence} onClose={() => setEvidence(null)} />
      <Sheet open={picker} onOpenChange={setPicker} title="Choose a meal">
        <h3 className="mb-2 text-lg font-bold">Choose a meal</h3>
        <ul className="divide-y divide-border">
          {recent.map((m) => {
            const mr = resultOf(m);
            return (
              <li key={m.id}>
                <button onClick={() => { setCurrent(m.id); setPicker(false); }} className={cn("flex min-h-14 w-full items-center justify-between text-left", m.id === meal.id && "text-primary")}>
                  <span><span className="block font-semibold">{m.label}, {timeOf(m.eaten_at)}</span><span className="text-xs text-muted">{new Date(m.eaten_at).toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" })} · {m.items.map((i) => i.name).join(", ")}</span></span>
                  <span className="flex items-center gap-2 text-sm tabular">{mr.conflicts.length > 0 && <i className="h-2 w-2 rounded-full bg-inhibitor" aria-label="conflict" />}{mr.fractional_pct}%</span>
                </button>
              </li>
            );
          })}
        </ul>
        <Link href="/history" onClick={() => setPicker(false)} className="mt-2 flex min-h-11 items-center text-sm font-bold text-primary">All meals in History</Link>
      </Sheet>
    </div>
  );
}

export default function AbsorbPage() {
  return <Suspense><AbsorbInner /></Suspense>;
}
