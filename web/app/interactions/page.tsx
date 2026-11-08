"use client";
// Public interaction map with live "what if" meals, so judges can play without signing in.
import { useEffect, useState } from "react";
import type { EngineResult, InteractionGraph } from "@/lib/types";
import { api, useApi } from "@/lib/api";
import { mg, pct } from "@/lib/format";
import InteractionMap from "@/components/charts/InteractionMap";

const PRESETS = [
  { name: "Lentil curry + black tea", items: [{ food_code: "MOCK_LENTIL_CURRY", name: "Lentil curry", grams: 250 }, { food_code: "MOCK_BASMATI", name: "Rice", grams: 180 }], drinks: [{ food_code: "MOCK_BLACK_TEA", name: "Black tea", grams: 250, offset_min: 0 }] },
  { name: "Same, tea an hour later", items: [{ food_code: "MOCK_LENTIL_CURRY", name: "Lentil curry", grams: 250 }, { food_code: "MOCK_BASMATI", name: "Rice", grams: 180 }], drinks: [{ food_code: "MOCK_BLACK_TEA", name: "Black tea", grams: 250, offset_min: 60 }] },
  { name: "Curry + red pepper + orange juice", items: [{ food_code: "MOCK_LENTIL_CURRY", name: "Lentil curry", grams: 250 }, { food_code: "MOCK_RED_PEPPER", name: "Red pepper", grams: 80 }], drinks: [{ food_code: "MOCK_ORANGE_JUICE", name: "Orange juice", grams: 200, offset_min: 0 }] },
  { name: "Beef chilli + cheese", items: [{ food_code: "MOCK_BEEF_MINCE", name: "Beef mince", grams: 120 }, { food_code: "MOCK_KIDNEY_BEANS", name: "Kidney beans", grams: 120 }, { food_code: "MOCK_CHEDDAR", name: "Cheddar", grams: 40 }], drinks: [] },
  { name: "No meal (just the map)", items: [], drinks: [] },
];

export default function InteractionsPage() {
  const { data: graph } = useApi<InteractionGraph>("/engine/interactions");
  const [i, setI] = useState(0);
  const [result, setResult] = useState<EngineResult | null>(null);

  useEffect(() => {
    const p = PRESETS[i];
    if (!p.items.length) { setResult(null); return; }
    api.post<EngineResult>("/engine/score", { items: p.items, drinks: p.drinks }).then(setResult).catch(() => setResult(null));
  }, [i]);

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold">How iron absorption works</h1>
        <p className="text-sm text-ink-2">Some foods help your body take up iron, others block it. Pick a meal to see which interactions switch on.</p>
      </div>
      <div className="flex gap-2 overflow-x-auto -mx-4 px-4 pb-1">
        {PRESETS.map((p, k) => (
          <button key={p.name} onClick={() => setI(k)} aria-pressed={i === k}
            className={`shrink-0 text-sm px-3 py-1.5 rounded-full border ${i === k ? "border-brand bg-brand/10 font-semibold" : "border-border bg-surface"}`}>{p.name}</button>
        ))}
      </div>
      {result && (
        <div className="card p-3 flex justify-between text-sm tabular">
          <span>Eaten <strong>{mg(result.iron_mg, 1)}</strong></span>
          <span>Absorbed <strong className="text-brand">{mg(result.absorbed_mg)}</strong></span>
          <span>{pct(result.fractional_pct)}</span>
        </div>
      )}
      {graph ? <InteractionMap graph={graph} result={result} height={460} /> : <p className="text-muted animate-pulse">Loading map…</p>}
    </div>
  );
}
