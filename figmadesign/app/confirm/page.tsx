"use client";
// SCREEN 5: Confirm your meal (+ the photo error card state)
import { AlertCircle, CameraOff, CircleHelp, Info, Minus, Pencil, Plus, Search, Trash2 } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";
import { BackBar, Sheet } from "@/components/shell";
import { Button, Card, PageTitle, cn } from "@/components/ui/primitives";
import { hasDataGap, searchFoods } from "@/lib/engine/foods";
import { intakeFromPhoto, newKey, type DraftItem } from "@/lib/logic";
import { useStore } from "@/lib/store";

const hhmm = (base: string, offset: number) => {
  const d = new Date(Date.parse(base) + offset * 60000);
  return d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
};

function ConfirmInner() {
  const router = useRouter();
  const params = useSearchParams();
  const draft = useStore((s) => s.draft);
  const setDraft = useStore((s) => s.setDraft);
  const patch = useStore((s) => s.patchDraft);
  const save = useStore((s) => s.saveDraft);
  const [edit, setEdit] = useState<DraftItem | null>(null);
  const [adding, setAdding] = useState(false);
  const [q, setQ] = useState("");

  // Opened directly (prototype map / refresh): start from the design's demo meal.
  useEffect(() => {
    if (!draft || params.get("state")) {
      const err = params.get("state") === "error";
      setDraft({ items: err ? [] : intakeFromPhoto(), source: "photo", eaten_at: new Date(new Date().setHours(13, 0, 0, 0)).toISOString(), label: "Lunch", photo: err ? undefined : "/demo-meal.svg", error: err });
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const results = useMemo(() => searchFoods(q), [q]);
  if (!draft) return null;
  const items = draft.items;
  const setItems = (fn: (i: DraftItem[]) => DraftItem[]) => patch({ items: fn(items) });
  const gap = items.some((i) => i.food_code && hasDataGap(i.food_code));
  const unanswered = items.filter((i) => !i.food_code).length;

  if (draft.error) {
    return (
      <div className="space-y-5">
        <BackBar href="/add" />
        <PageTitle eyebrow="Check the details" title="Review your meal" />
        <Card className="border-inhibitor/30 p-5 text-center">
          <span className="mx-auto grid h-14 w-14 place-items-center rounded-full bg-inhibitor/12 text-inhibitor"><CameraOff className="h-6 w-6" /></span>
          <p className="mt-3 font-bold">We couldn&apos;t read that photo.</p>
          <p className="mt-1 text-sm text-muted">Try again or describe your meal.</p>
          <div className="mt-4 grid grid-cols-2 gap-2">
            <Button variant="secondary" href="/add">Try again</Button>
            <Button href="/add?tab=description">Describe meal</Button>
          </div>
        </Card>
      </div>
    );
  }

  function confirm() {
    const m = save();
    if (m) router.push("/absorb?new=1");
  }

  return (
    <div className="space-y-4">
      <BackBar href="/add" />
      <PageTitle eyebrow="Check the details" title="Confirm your meal" right={<span className="rounded-full bg-surface-2 px-3 py-1 text-xs font-semibold text-muted">2 of 2</span>} />

      {draft.photo && (
        <motion.div initial={{ opacity: 0, scale: 0.98 }} animate={{ opacity: 1, scale: 1 }} className="relative h-36 overflow-hidden rounded-2xl">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={draft.photo} alt="Your meal" className="h-full w-full object-cover" />
          <span className="absolute bottom-2 left-2 rounded-full bg-black/55 px-2.5 py-1 text-xs font-semibold text-white">{draft.label} · {hhmm(draft.eaten_at, 0)}</span>
        </motion.div>
      )}

      <Card className="divide-y divide-border">
        <AnimatePresence initial={false}>
          {items.map((it) => (
            <motion.div key={it.key} layout initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0, height: 0 }} className="overflow-hidden">
              <div className="flex min-h-16 items-center gap-3 px-4 py-3">
                <span className={cn("grid h-10 w-10 shrink-0 place-items-center rounded-full text-sm font-bold", it.is_drink ? "bg-amber/15 text-amber" : "bg-primary/10 text-primary")}>
                  {(it.name ?? it.detected ?? "?")[0].toUpperCase()}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate font-semibold">{it.name ?? `“${it.detected}”`}</p>
                  <p className="text-sm text-muted tabular">{it.is_drink ? `1 cup, ${hhmm(draft.eaten_at, it.offset_min)}` : `${it.grams} g`}</p>
                </div>
                <button onClick={() => setEdit(it)} aria-label={`Edit ${it.name ?? it.detected}`} className="grid h-11 w-11 place-items-center rounded-xl text-muted hover:bg-surface-2"><Pencil className="h-[18px] w-[18px]" /></button>
                <button onClick={() => setItems((xs) => xs.filter((x) => x.key !== it.key))} aria-label={`Remove ${it.name ?? it.detected}`} className="grid h-11 w-11 place-items-center rounded-xl text-muted hover:bg-surface-2"><Trash2 className="h-[18px] w-[18px]" /></button>
              </div>
              {!it.food_code && (
                <div className="mx-4 mb-3 rounded-xl bg-amber/14 p-3">
                  <p className="flex items-center gap-2 text-sm font-bold"><CircleHelp className="h-4 w-4 text-amber" />{it.question ?? "Which one is it?"}</p>
                  <div className="mt-2 grid grid-cols-2 gap-2">
                    {it.candidates.map((c) => (
                      <button key={c.food_code} onClick={() => setItems((xs) => xs.map((x) => (x.key === it.key ? { ...x, food_code: c.food_code, name: c.name, question: undefined } : x)))}
                        className="min-h-11 rounded-xl border border-amber/40 bg-surface text-sm font-semibold hover:bg-amber/10">{c.name}</button>
                    ))}
                  </div>
                </div>
              )}
            </motion.div>
          ))}
        </AnimatePresence>
        {!items.length && <p className="p-4 text-sm text-muted">No items left. Add one below.</p>}
      </Card>

      {gap && (
        <div className="flex gap-2 rounded-xl bg-surface-2 p-3 text-sm text-muted">
          <Info className="mt-0.5 h-4 w-4 shrink-0" />Inhibitor data not available. This estimate may be high.
        </div>
      )}

      <button onClick={() => setAdding(true)} className="flex min-h-11 items-center gap-1.5 text-sm font-bold text-primary"><Plus className="h-4 w-4" />Add item</button>

      <div className="sticky-cta">
        <Button size="lg" className="w-full" disabled={!items.length || unanswered > 0} onClick={confirm}>
          {unanswered ? <><AlertCircle className="h-4 w-4" />Answer the question above</> : <>Confirm and score meal <span aria-hidden>→</span></>}
        </Button>
      </div>

      {/* Edit amount / time */}
      <Sheet open={!!edit} onOpenChange={(o) => !o && setEdit(null)} title="Edit item">
        {edit && (
          <div className="space-y-5">
            <h3 className="text-lg font-bold">{edit.name ?? edit.detected}</h3>
            <div className="flex items-center justify-between">
              <span className="text-sm font-semibold">{edit.is_drink ? "Amount (ml)" : "Amount (g)"}</span>
              <div className="flex items-center gap-3">
                <button className="grid h-11 w-11 place-items-center rounded-full bg-surface-2" aria-label="Less" onClick={() => setEdit({ ...edit, grams: Math.max(10, edit.grams - 25) })}><Minus className="h-4 w-4" /></button>
                <span className="w-16 text-center text-xl font-bold tabular">{edit.grams}</span>
                <button className="grid h-11 w-11 place-items-center rounded-full bg-surface-2" aria-label="More" onClick={() => setEdit({ ...edit, grams: edit.grams + 25 })}><Plus className="h-4 w-4" /></button>
              </div>
            </div>
            {edit.is_drink && (
              <label className="flex items-center justify-between">
                <span className="text-sm font-semibold">Drunk at</span>
                <input type="time" className="h-11 rounded-xl border border-border bg-surface px-3" value={hhmm(draft.eaten_at, edit.offset_min)}
                  onChange={(e) => { const [h, m] = e.target.value.split(":").map(Number); const base = new Date(draft.eaten_at); setEdit({ ...edit, offset_min: h * 60 + m - (base.getHours() * 60 + base.getMinutes()) }); }} />
              </label>
            )}
            <Button size="lg" className="w-full" onClick={() => { setItems((xs) => xs.map((x) => (x.key === edit.key ? edit : x))); setEdit(null); }}>Save</Button>
          </div>
        )}
      </Sheet>

      {/* Add item */}
      <Sheet open={adding} onOpenChange={setAdding} title="Add item">
        <label className="flex h-12 items-center gap-2 rounded-2xl border border-border bg-surface-2 px-4">
          <Search className="h-5 w-5 text-faint" />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search foods and drinks" className="flex-1 bg-transparent outline-none" />
        </label>
        <ul className="mt-2 max-h-[50vh] divide-y divide-border overflow-y-auto">
          {results.map((f) => (
            <li key={f.food_code}>
              <button className="flex min-h-12 w-full items-center justify-between text-left" onClick={() => {
                setItems((xs) => [...xs, { key: newKey(), food_code: f.food_code, name: f.name, grams: f.serving_g, is_drink: !!f.is_drink, offset_min: 0, candidates: [] }]);
                setAdding(false); setQ("");
              }}>
                <span className="text-sm font-semibold">{f.name}</span><span className="text-xs text-muted">{f.serving_g} {f.is_drink ? "ml" : "g"}</span>
              </button>
            </li>
          ))}
        </ul>
      </Sheet>
    </div>
  );
}

export default function ConfirmPage() {
  return <Suspense><ConfirmInner /></Suspense>;
}
