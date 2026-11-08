"use client";
// SCREEN 3: Add meal (Add image / Description / Search item states)
import { Camera, Check, ImagePlus, Search, X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useMemo, useRef, useState } from "react";
import { Button, Card, PageTitle, Segmented, cn } from "@/components/ui/primitives";
import { searchFoods } from "@/lib/engine/foods";
import type { Food } from "@/lib/engine/types";
import { DEMO_PHOTO, DRINK_CHIPS, drinkRow, newKey, type DraftItem } from "@/lib/logic";
import { useStore } from "@/lib/store";

type Tab = "image" | "description" | "search";
const nowHHMM = () => new Date().toTimeString().slice(0, 5);
const labelFor = (h: number) => (h < 11 ? "Breakfast" : h < 16 ? "Lunch" : h < 21 ? "Dinner" : "Snack");
const toMin = (t: string) => { const [h, m] = t.split(":").map(Number); return h * 60 + m; };

async function shrink(file: File): Promise<string> {
  const bmp = await createImageBitmap(file); // throws for unreadable files → error card on Confirm
  const s = Math.min(1, 900 / Math.max(bmp.width, bmp.height));
  const c = document.createElement("canvas");
  c.width = bmp.width * s; c.height = bmp.height * s;
  c.getContext("2d")!.drawImage(bmp, 0, 0, c.width, c.height);
  return c.toDataURL("image/jpeg", 0.8);
}

function AddMealInner() {
  const router = useRouter();
  const setDraft = useStore((s) => s.setDraft);
  const initial = useSearchParams().get("tab");
  const [tab, setTab] = useState<Tab>(initial === "description" || initial === "search" ? initial : "image");
  const [photo, setPhoto] = useState<string | null>(null);
  const [photoError, setPhotoError] = useState(false);
  const [text, setText] = useState("");
  const [q, setQ] = useState("");
  const [picked, setPicked] = useState<Food[]>([]);
  const [when, setWhen] = useState<"now" | "pick">("now");
  const [time, setTime] = useState(nowHHMM());
  const [drinks, setDrinks] = useState<Record<string, string>>({ Tea: nowHHMM() });
  const [none, setNone] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const results = useMemo(() => searchFoods(q).filter((f) => !f.is_drink), [q]);

  const mealTime = when === "now" ? nowHHMM() : time;
  const toggleDrink = (label: string) => {
    setNone(false);
    setDrinks((d) => { const n = { ...d }; if (n[label]) delete n[label]; else n[label] = mealTime; return n; });
  };

  async function onFile(f?: File) {
    if (!f) return;
    try { setPhoto(await shrink(f)); setPhotoError(false); } catch { setPhoto(null); setPhotoError(true); }
  }

  const canReview = tab === "image" ? !!photo || photoError : tab === "description" ? text.trim().length > 2 : picked.length > 0;

  function review() {
    const eaten = new Date();
    if (when === "pick") { const [h, m] = time.split(":").map(Number); eaten.setHours(h, m, 0, 0); }
    // Drinks chosen below override any drink the photo/description found.
    const chosen = Object.entries(drinks);
    const extraDrinks: DraftItem[] = none ? [] : chosen.map(([label, t]) => drinkRow(label, toMin(t) - toMin(mealTime)));
    const base = { source: (tab === "image" ? "photo" : tab === "description" ? "text" : "manual") as "photo" | "text" | "manual",
      eaten_at: eaten.toISOString(), label: labelFor(eaten.getHours()) };
    if (tab === "search") {
      const items: DraftItem[] = picked.map((f) => ({ key: newKey(), food_code: f.food_code, name: f.name, grams: f.serving_g, is_drink: false, offset_min: 0, candidates: [] }));
      setDraft({ ...base, items: [...items, ...extraDrinks] });
      router.push("/confirm");
      return;
    }
    // Photo or description: the Analysing screen sends it to the intake agent (Gemini), then on to Confirm.
    setDraft({ ...base, items: [], extraDrinks, dropDrinks: chosen.length > 0 || none,
      photo: photo ?? undefined, text: tab === "description" ? text : undefined, error: tab === "image" && photoError });
    router.push(photoError && tab === "image" ? "/confirm" : "/analysing");
  }

  return (
    <div className="space-y-5 pb-4">
      <PageTitle eyebrow="Track absorption" title="Add a meal" right={<span className="rounded-full bg-surface-2 px-3 py-1 text-xs font-semibold text-muted">1 of 2</span>} />

      <Segmented id="add" value={tab} onChange={setTab} options={[
        { value: "image", label: "Add image" }, { value: "description", label: "Description" }, { value: "search", label: "Search item" }]} />

      <AnimatePresence mode="wait">
        <motion.div key={tab} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }} transition={{ duration: 0.18 }}>
          {tab === "image" && (
            <div className="space-y-2">
              <input ref={fileRef} type="file" accept="image/*" capture="environment" className="hidden" onChange={(e) => onFile(e.target.files?.[0])} />
              <button onClick={() => fileRef.current?.click()}
                className="relative grid aspect-[4/3] w-full place-items-center overflow-hidden rounded-2xl border-2 border-dashed border-primary/35 bg-primary/[0.04] transition-colors hover:bg-primary/[0.07]">
                {photo ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={photo} alt="Your meal" className="absolute inset-0 h-full w-full object-cover" />
                ) : (
                  <span className="flex flex-col items-center gap-2 text-center">
                    <span className="grid h-16 w-16 place-items-center rounded-full bg-primary/12 text-primary"><Camera className="h-7 w-7" /></span>
                    <strong>Take a photo or choose one</strong>
                    <small className="text-muted">We&apos;ll identify the foods for you</small>
                  </span>
                )}
              </button>
              {photoError && <p className="text-sm text-inhibitor">That file couldn&apos;t be read. You can still continue to see the error state.</p>}
              {!photo && (
                <button onClick={() => { setPhoto(DEMO_PHOTO); setPhotoError(false); }} className="flex min-h-11 items-center gap-2 text-sm font-semibold text-primary">
                  <ImagePlus className="h-4 w-4" />Use the demo photo
                </button>
              )}
            </div>
          )}

          {tab === "description" && (
            <div className="space-y-3">
              <label className="block">
                <span className="text-sm font-semibold">Describe your meal</span>
                <textarea value={text} onChange={(e) => setText(e.target.value)} placeholder="lentil curry and a cup of tea"
                  className="mt-2 min-h-32 w-full rounded-2xl border border-border bg-surface p-4 text-[15px] outline-none placeholder:text-faint focus:border-primary" />
              </label>
              <Button className="w-full" disabled={text.trim().length < 3} onClick={review}>Analyse</Button>
            </div>
          )}

          {tab === "search" && (
            <div className="space-y-3">
              <label className="flex h-12 items-center gap-2 rounded-2xl border border-border bg-surface px-4 focus-within:border-primary">
                <Search className="h-5 w-5 text-faint" />
                <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search foods" className="flex-1 bg-transparent outline-none placeholder:text-faint" />
              </label>
              {picked.length > 0 && (
                <div className="flex flex-wrap gap-2">
                  {picked.map((f) => (
                    <button key={f.food_code} onClick={() => setPicked((p) => p.filter((x) => x.food_code !== f.food_code))}
                      className="flex items-center gap-1 rounded-full bg-primary/12 py-1 pl-3 pr-2 text-xs font-semibold text-primary">{f.name}<X className="h-3.5 w-3.5" /></button>
                  ))}
                </div>
              )}
              <Card className="divide-y divide-border overflow-hidden">
                {results.map((f) => {
                  const on = picked.some((p) => p.food_code === f.food_code);
                  return (
                    <button key={f.food_code} onClick={() => setPicked((p) => (on ? p.filter((x) => x.food_code !== f.food_code) : [...p, f]))}
                      className="flex min-h-14 w-full items-center justify-between px-4 text-left hover:bg-surface-2">
                      <span><span className="block text-sm font-semibold">{f.name}</span><span className="text-xs text-muted">Serving {f.serving_g} g · {f.iron_mg} mg iron per 100 g</span></span>
                      <span className={cn("grid h-7 w-7 place-items-center rounded-full border", on ? "border-primary bg-primary text-primary-ink" : "border-border")}>{on && <Check className="h-4 w-4" />}</span>
                    </button>
                  );
                })}
                {!results.length && <p className="p-4 text-sm text-muted">No foods match “{q}”.</p>}
              </Card>
            </div>
          )}
        </motion.div>
      </AnimatePresence>

      <section className="space-y-2">
        <h2 className="font-bold">When did you eat?</h2>
        <Segmented id="when" value={when} onChange={setWhen} options={[{ value: "now", label: "Now" }, { value: "pick", label: "Pick a time" }]} />
        {when === "pick" && <input type="time" value={time} onChange={(e) => setTime(e.target.value)} className="h-12 w-full rounded-2xl border border-border bg-surface px-4 text-[15px]" aria-label="Meal time" />}
      </section>

      <section className="space-y-2">
        <h2 className="font-bold">Any drinks?</h2>
        <p className="text-sm text-muted">Drinks can change iron absorption, and so can their timing.</p>
        <div className="flex flex-wrap gap-2">
          {[...DRINK_CHIPS.map((d) => d.label), "None"].map((label) => {
            const on = label === "None" ? none : !!drinks[label];
            return (
              <button key={label} onClick={() => (label === "None" ? (setNone(true), setDrinks({})) : toggleDrink(label))} aria-pressed={on}
                className={cn("flex min-h-11 items-center gap-1.5 rounded-full border px-4 text-sm font-semibold transition-colors", on ? "border-primary bg-primary text-primary-ink" : "border-border bg-surface text-ink")}>
                {on && <Check className="h-4 w-4" />}{label}
              </button>
            );
          })}
        </div>
        <AnimatePresence>
          {Object.entries(drinks).map(([label, t]) => (
            <motion.label key={label} initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }}
              className="flex items-center justify-between overflow-hidden rounded-xl bg-surface-2 px-4 py-2 text-sm">
              <span className="font-semibold">{label} at</span>
              <input type="time" value={t} onChange={(e) => setDrinks((d) => ({ ...d, [label]: e.target.value }))} className="h-9 rounded-lg bg-surface px-2" aria-label={`${label} time`} />
            </motion.label>
          ))}
        </AnimatePresence>
      </section>

      {tab !== "description" && (
        <div className="sticky-cta">
          <Button size="lg" className="w-full" disabled={!canReview} onClick={review}>Review meal <span aria-hidden>→</span></Button>
        </div>
      )}
    </div>
  );
}

export default function AddMeal() {
  return <Suspense><AddMealInner /></Suspense>;
}
