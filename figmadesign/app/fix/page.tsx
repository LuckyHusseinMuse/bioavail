"use client";
// SCREEN 10: Fix suggestions
import * as Collapsible from "@radix-ui/react-collapsible";
import { ArrowUpRight, BellRing, ChevronDown, Plus, Sparkles, TrendingUp } from "lucide-react";
import { motion } from "motion/react";
import { useMemo, useState } from "react";
import { toast } from "sonner";
import EvidenceSheet from "@/components/EvidenceSheet";
import { BackBar } from "@/components/shell";
import { Bar, Button, Card, Chip, EmptyState, PageTitle } from "@/components/ui/primitives";
import { findFixes, type Fix } from "@/lib/logic";
import { timeOf, useStore, type Meal } from "@/lib/store";

const mg = (n: number) => (n < 0.1 ? n.toFixed(3) : n.toFixed(2));
const clock = (iso: string, plus: number) => timeOf(new Date(Date.parse(iso) + plus * 60000).toISOString());

/** Lunch at 13:00 with the shaded one-hour window, the tea marker now, and the dashed marker where it would move. */
function TimelineStrip({ meal, fix }: { meal: Meal; fix?: Fix }) {
  const drink = meal.drinks.find((d) => d.food_code === fix?.change.food_code) ?? meal.drinks[0];
  const W = 320, start = -30, end = 180;
  const x = (m: number) => 14 + ((m - start) / (end - start)) * (W - 28);
  return (
    <Card className="p-4">
      <div className="flex justify-between text-sm"><strong>{meal.label}</strong><span className="text-muted tabular">{timeOf(meal.eaten_at)}</span></div>
      <svg viewBox={`0 0 ${W} 92`} className="mt-2 w-full" role="img" aria-label="Meal timing">
        <rect x={x(0)} y={8} width={x(60) - x(0)} height={52} rx={10} fill="var(--primary)" opacity={0.12} />
        <text x={x(30)} y={22} textAnchor="middle" fontSize={9} fill="var(--primary)" fontWeight={700}>1-hour window</text>
        <line x1={x(start)} x2={x(end)} y1={62} y2={62} stroke="var(--border)" strokeWidth={2} />
        {[0, 60, 120, 180].map((m) => (
          <g key={m}><line x1={x(m)} x2={x(m)} y1={58} y2={66} stroke="var(--faint)" /><text x={x(m)} y={82} textAnchor="middle" fontSize={10} fill="var(--muted)">{clock(meal.eaten_at, m)}</text></g>
        ))}
        <circle cx={x(0)} cy={62} r={6} fill="var(--primary)" stroke="var(--surface)" strokeWidth={2} />
        {drink && (
          <g>
            <circle cx={x(drink.offset_min)} cy={40} r={9} fill="var(--inhibitor)" stroke="var(--surface)" strokeWidth={2} />
            <text x={x(drink.offset_min)} y={44} textAnchor="middle" fontSize={9} fill="#fff" fontWeight={800}>!</text>
          </g>
        )}
        {fix?.change.kind === "retime" && (
          <motion.g initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.3 }}>
            <line x1={x(drink?.offset_min ?? 0) + 11} x2={x(fix.change.offset_min!) - 11} y1={40} y2={40} stroke="var(--enhancer)" strokeDasharray="4 4" strokeWidth={2} />
            <circle cx={x(fix.change.offset_min!)} cy={40} r={9} fill="var(--surface)" stroke="var(--enhancer)" strokeWidth={2} strokeDasharray="3 3" />
          </motion.g>
        )}
      </svg>
      <p className="mt-1 text-xs text-muted">{drink ? `${drink.name} at ${clock(meal.eaten_at, drink.offset_min)} sits inside the window. Moving it outside reduces the conflict.` : "No drinks with this meal."}</p>
    </Card>
  );
}

function FixCard({ f, meal, onEvidence, i }: { f: Fix; meal: Meal; onEvidence: (id: string) => void; i: number }) {
  const applyFix = useStore((s) => s.applyFix);
  const addReminder = useStore((s) => s.addReminder);
  const addAlert = useStore((s) => s.addAlert);
  const max = Math.max(f.after, f.before);
  const gainPct = f.before ? Math.round((f.gain / f.before) * 100) : 0;

  function act() {
    if (f.action === "remind") {
      const at = clock(meal.eaten_at, f.change.offset_min ?? 120);
      addReminder({ kind: "drink", title: `Have your ${f.change.name?.toLowerCase() ?? "drink"}`, time: at, repeat: "once", days: [], notify: true });
      addAlert({ type: "timing", title: `You can have your ${f.change.name?.toLowerCase().replace(/^black /, "") ?? "drink"} at ${at}`, detail: `Reminder for ${meal.label.toLowerCase()}`, meal_id: meal.id });
      applyFix(meal.id, f.change);
      toast.success(`Reminder set for ${at}`);
    } else {
      applyFix(meal.id, f.change);
      toast.success(`${f.change.replace_with_name ?? f.change.name} added to this meal`);
    }
  }

  return (
    <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 + i * 0.1 }}>
      <Card className="p-5">
        <div className="flex items-start justify-between gap-3">
          <div><h2 className="font-bold leading-snug">{f.title}</h2><p className="text-sm text-muted">{f.detail}</p></div>
          <Chip tone="green" icon={<TrendingUp className="h-3.5 w-3.5" />} className="shrink-0">+{gainPct}%</Chip>
        </div>
        <div className="mt-4 space-y-2.5">
          <div className="flex items-center gap-3 text-sm"><span className="w-10 text-muted">Now</span><Bar pct={(f.before / max) * 100} color="var(--faint)" /><strong className="w-[76px] shrink-0 whitespace-nowrap text-right tabular">{mg(f.before)} mg</strong></div>
          <div className="flex items-center gap-3 text-sm"><span className="w-10 text-muted">After</span><Bar pct={(f.after / max) * 100} color="var(--enhancer)" delay={0.2} /><strong className="w-[76px] shrink-0 whitespace-nowrap text-right tabular">{mg(f.after)} mg</strong></div>
        </div>
        <p className="mt-1 text-right text-[11px] text-faint">absorbed · Not medical advice</p>
        <div className="mt-3 flex items-center justify-between gap-2">
          <button onClick={() => onEvidence(f.evidence)} className="inline-flex min-h-11 items-center gap-1 text-sm font-bold text-primary">Evidence <ArrowUpRight className="h-4 w-4" /></button>
          <Button onClick={act} variant={i === 0 ? "primary" : "secondary"}>{f.action === "remind" ? <><BellRing className="h-4 w-4" />Remind me</> : <><Plus className="h-4 w-4" />Add to meal</>}</Button>
        </div>
      </Card>
    </motion.div>
  );
}

export default function FixPage() {
  const meals = useStore((s) => s.meals);
  const currentId = useStore((s) => s.currentMealId);
  const avoid = useStore((s) => s.profile.avoid);
  const [open, setOpen] = useState(false);
  const [evidence, setEvidence] = useState<string | null>(null);
  const meal = meals.find((m) => m.id === currentId) ?? meals.at(-1);
  const fixes = useMemo(() => (meal ? findFixes(meal.items, meal.drinks, avoid) : null), [meal, avoid]);

  if (!meal || !fixes) return <EmptyState icon={<Sparkles className="h-7 w-7" />} title="No meal to fix" action={<Button href="/add">Add a meal</Button>} />;
  const best = fixes.ranked.slice(0, 2);
  const rest = fixes.ranked.slice(2);

  return (
    <div className="space-y-4">
      <BackBar href="/absorb" />
      <PageTitle eyebrow="Best next step" title="Smallest changes that help most" />
      <Collapsible.Root open={open} onOpenChange={setOpen}>
        <Collapsible.Trigger className="flex min-h-10 items-center gap-1 text-sm text-muted">
          Checked {fixes.checked} changes, showing the best {best.length}
          <ChevronDown className={`h-4 w-4 transition-transform ${open ? "rotate-180" : ""}`} />
        </Collapsible.Trigger>
        <Collapsible.Content className="overflow-hidden data-[state=open]:animate-in">
          <ul className="mt-1 divide-y divide-border rounded-2xl border border-border bg-surface text-sm">
            {rest.map((f) => <li key={f.id} className="flex justify-between gap-3 px-4 py-2.5"><span>{f.title}</span><span className="shrink-0 text-muted tabular">+{mg(f.gain)} mg</span></li>)}
            {fixes.checked - fixes.ranked.length > 0 && <li className="px-4 py-2.5 text-muted">{fixes.checked - fixes.ranked.length} more made no difference</li>}
            {!rest.length && fixes.checked - fixes.ranked.length === 0 && <li className="px-4 py-2.5 text-muted">No other changes helped.</li>}
          </ul>
        </Collapsible.Content>
      </Collapsible.Root>

      {meal.drinks.length > 0 && <TimelineStrip meal={meal} fix={best.find((f) => f.change.kind === "retime")} />}
      {best.length ? best.map((f, i) => <FixCard key={f.id} f={f} meal={meal} i={i} onEvidence={setEvidence} />)
        : <EmptyState icon={<Sparkles className="h-7 w-7" />} title="This meal is already in good shape" body="No small change improves it much." />}
      <EvidenceSheet id={evidence} onClose={() => setEvidence(null)} />
    </div>
  );
}
