"use client";
// Log a meal: photo / text / manual search → intake agent → CONFIRM screen → save.
// Nothing is saved until the user presses "Save meal" (guardrail: approval before save_meal).
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import type { Food, IntakeCandidate, IntakeResponse, SavedMeal } from "@/lib/types";
import { api, fileToJpegBase64 } from "@/lib/api";
import FoodSearch from "@/components/FoodSearch";
import { notifyAlertsChanged } from "@/components/AppShell";
import { IconCamera, IconSearch, IconText, IconX } from "@/components/Icons";

type Row = {
  key: string;
  detected?: string;
  food_code: string | null;
  name: string | null;
  grams: number;
  is_drink: boolean;
  offset_min: number;
  candidates: IntakeCandidate[];
  question?: string;
};

const TIMING = [
  { v: -60, l: "1 h before" },
  { v: 0, l: "With the meal" },
  { v: 30, l: "30 min after" },
  { v: 60, l: "1 h after" },
  { v: 120, l: "2 h after" },
];

const defaultLabel = () => {
  const h = new Date().getHours();
  return h < 11 ? "Breakfast" : h < 16 ? "Lunch" : h < 21 ? "Dinner" : "Snack";
};
let k = 0;
const key = () => `r${k++}`;

export default function LogPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"photo" | "text" | "search">("photo");
  const [step, setStep] = useState<"input" | "confirm">("input");
  const [text, setText] = useState("");
  const [preview, setPreview] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [rows, setRows] = useState<Row[]>([]);
  const [label, setLabel] = useState(defaultLabel());
  const [notes, setNotes] = useState<string | null>(null);
  const [searchFor, setSearchFor] = useState<string | "new" | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const fromIntake = (r: IntakeResponse) => {
    const qs = new Map(r.questions.map((q) => [q.item_index, q]));
    setRows(r.items.map((it, i) => ({
      key: key(), detected: it.detected, food_code: it.food_code, name: it.name, grams: it.grams, is_drink: it.is_drink,
      offset_min: it.offset_min ?? 0, candidates: qs.get(i)?.options ?? it.candidates, question: qs.get(i)?.question,
    })));
    setNotes(r.notes ?? null);
    setStep("confirm");
  };

  async function runIntake(body: Record<string, unknown>) {
    setError(null);
    setBusy("Identifying foods…");
    try {
      fromIntake(await api.post<IntakeResponse>("/agent/intake", body));
    } catch (e) {
      setError(`${(e as Error).message}. You can add foods by search instead.`);
    } finally {
      setBusy(null);
    }
  }

  async function onPhoto(file?: File) {
    if (!file) return;
    try {
      const img = await fileToJpegBase64(file);
      setPreview(img.previewUrl);
      await runIntake({ image_base64: img.base64, mime_type: img.mime, text: text || undefined });
    } catch {
      setError("Couldn't read that image. Try another photo.");
    }
  }

  const addFood = (f: Food) => {
    const row: Row = { key: key(), food_code: f.food_code, name: f.name, grams: f.serving_g, is_drink: !!f.is_drink, offset_min: 0, candidates: [] };
    if (searchFor && searchFor !== "new") setRows((rs) => rs.map((r) => (r.key === searchFor ? { ...r, food_code: f.food_code, name: f.name, question: undefined } : r)));
    else setRows((rs) => [...rs, row]);
    setSearchFor(null);
    setStep("confirm");
  };

  const update = (k: string, patch: Partial<Row>) => setRows((rs) => rs.map((r) => (r.key === k ? { ...r, ...patch } : r)));
  const unresolved = rows.filter((r) => !r.food_code);

  async function save() {
    setBusy("Saving and scoring…");
    setError(null);
    try {
      const saved = await api.post<SavedMeal>("/meals", {
        label,
        eaten_at: new Date().toISOString(),
        source: mode === "search" ? "manual" : mode,
        items: rows.filter((r) => !r.is_drink).map((r) => ({ food_code: r.food_code, name: r.name, grams: r.grams })),
        drinks: rows.filter((r) => r.is_drink).map((r) => ({ food_code: r.food_code, name: r.name, grams: r.grams, offset_min: r.offset_min })),
      });
      notifyAlertsChanged();
      router.push(`/meal/${saved.meal.id}`);
    } catch (e) {
      setError((e as Error).message);
      setBusy(null);
    }
  }

  // ---------- render ----------
  if (searchFor) {
    return (
      <div>
        <div className="flex items-center justify-between mb-3">
          <h1 className="text-xl font-bold">Find a food</h1>
          <button onClick={() => setSearchFor(null)} className="p-2 text-muted" aria-label="Close"><IconX /></button>
        </div>
        <FoodSearch onPick={addFood} autoFocus />
      </div>
    );
  }

  if (step === "confirm") {
    return (
      <div className="space-y-4">
        <div>
          <h1 className="text-xl font-bold">Check your meal</h1>
          <p className="text-sm text-ink-2">Fix anything we got wrong. Nothing is saved until you press Save.</p>
        </div>
        {preview && (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={preview} alt="Your meal" className="w-full h-40 object-cover rounded-2xl" />
        )}
        {notes && <p className="text-sm text-ink-2">{notes}</p>}

        <label className="block">
          <span className="text-xs text-ink-2">Meal</span>
          <select className="input mt-1" value={label} onChange={(e) => setLabel(e.target.value)}>
            {["Breakfast", "Lunch", "Dinner", "Snack"].map((l) => <option key={l}>{l}</option>)}
          </select>
        </label>

        <ul className="space-y-3">
          {rows.map((r) => (
            <li key={r.key} className={`card p-3 ${!r.food_code ? "ring-2 ring-warning" : ""}`}>
              <div className="flex justify-between gap-2">
                <div>
                  <div className="font-medium">{r.name ?? `“${r.detected}”`}</div>
                  {r.detected && r.name && <div className="text-xs text-muted">seen as “{r.detected}”</div>}
                </div>
                <button onClick={() => setRows((rs) => rs.filter((x) => x.key !== r.key))} className="text-muted p-1 -m-1" aria-label={`Remove ${r.name ?? r.detected}`}><IconX className="w-5 h-5" /></button>
              </div>

              {!r.food_code && (
                <div className="mt-2">
                  <p className="text-sm font-medium">{r.question ?? "Which one is it?"}</p>
                  <div className="flex flex-wrap gap-2 mt-2">
                    {r.candidates.map((c) => (
                      <button key={c.food_code} className="btn btn-ghost !min-h-9 !py-1.5 text-sm" onClick={() => update(r.key, { food_code: c.food_code, name: c.name, question: undefined })}>{c.name}</button>
                    ))}
                    <button className="btn btn-ghost !min-h-9 !py-1.5 text-sm" onClick={() => setSearchFor(r.key)}><IconSearch className="w-4 h-4" />Search</button>
                  </div>
                </div>
              )}

              <div className="flex gap-3 mt-3">
                <label className="flex-1">
                  <span className="text-xs text-ink-2">{r.is_drink ? "Amount (ml)" : "Amount (g)"}</span>
                  <input type="number" inputMode="numeric" min={1} className="input mt-1 tabular" value={r.grams} onChange={(e) => update(r.key, { grams: Math.max(1, Number(e.target.value)) })} />
                </label>
                {r.is_drink && (
                  <label className="flex-1">
                    <span className="text-xs text-ink-2">When</span>
                    <select className="input mt-1" value={r.offset_min} onChange={(e) => update(r.key, { offset_min: Number(e.target.value) })}>
                      {TIMING.map((t) => <option key={t.v} value={t.v}>{t.l}</option>)}
                    </select>
                  </label>
                )}
              </div>
            </li>
          ))}
        </ul>

        <button className="btn btn-ghost w-full" onClick={() => setSearchFor("new")}>+ Add a food or drink</button>
        {error && <p className="text-sm text-critical">{error}</p>}
        <div className="flex gap-3">
          <button className="btn btn-ghost" onClick={() => { setStep("input"); setRows([]); setPreview(null); }}>Start over</button>
          <button className="btn btn-primary flex-1" disabled={!rows.length || unresolved.length > 0 || !!busy} onClick={save}>
            {busy ?? (unresolved.length ? `Answer ${unresolved.length} question${unresolved.length > 1 ? "s" : ""}` : "Save meal")}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">Log a meal</h1>
      <div className="grid grid-cols-3 gap-1 p-1 bg-surface-2 rounded-xl" role="tablist">
        {([["photo", "Photo", IconCamera], ["text", "Describe", IconText], ["search", "Search", IconSearch]] as const).map(([m, l, I]) => (
          <button key={m} role="tab" aria-selected={mode === m} onClick={() => setMode(m)} className={`flex items-center justify-center gap-1.5 py-2 rounded-lg text-sm font-medium ${mode === m ? "bg-surface shadow-sm" : "text-ink-2"}`}>
            <I className="w-4 h-4" />{l}
          </button>
        ))}
      </div>

      {mode === "photo" && (
        <div className="space-y-3">
          <input ref={fileRef} type="file" accept="image/*" capture="environment" className="hidden" onChange={(e) => onPhoto(e.target.files?.[0])} />
          <button onClick={() => fileRef.current?.click()} disabled={!!busy} className="card w-full aspect-[4/3] grid place-items-center text-ink-2 border-dashed border-2">
            {preview ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={preview} alt="" className="w-full h-full object-cover rounded-2xl" />
            ) : (
              <span className="flex flex-col items-center gap-2"><IconCamera className="w-10 h-10" />Take or choose a photo</span>
            )}
          </button>
          <input className="input" placeholder="Optional: add a note, e.g. “with black tea”" value={text} onChange={(e) => setText(e.target.value)} />
          <p className="text-xs text-muted">Include drinks in the photo. Tea and coffee matter as much as the food.</p>
        </div>
      )}

      {mode === "text" && (
        <div className="space-y-3">
          <textarea className="input min-h-32" placeholder="e.g. lentil curry with rice and a cup of tea" value={text} onChange={(e) => setText(e.target.value)} />
          <button className="btn btn-primary w-full" disabled={!text.trim() || !!busy} onClick={() => runIntake({ text })}>Identify foods</button>
        </div>
      )}

      {mode === "search" && <FoodSearch onPick={addFood} />}

      {busy && <p className="text-sm text-brand animate-pulse">{busy}</p>}
      {error && <p className="text-sm text-critical">{error}</p>}
    </div>
  );
}
