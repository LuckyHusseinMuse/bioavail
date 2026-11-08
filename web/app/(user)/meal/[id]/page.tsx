"use client";
import Link from "next/link";
import { use, useEffect, useState } from "react";
import type { Analysis, FixResponse, InteractionGraph, SavedMeal } from "@/lib/types";
import { api, useApi } from "@/lib/api";
import { mg, pct, time } from "@/lib/format";
import CitedText from "@/components/CitedText";
import EvidenceSheet from "@/components/EvidenceSheet";
import { notifyAlertsChanged } from "@/components/AppShell";
import { IconAlert, IconCheck, IconClock, IconSpark } from "@/components/Icons";
import InteractionMap from "@/components/charts/InteractionMap";
import Waterfall from "@/components/charts/Waterfall";
import BeforeAfter from "@/components/charts/BeforeAfter";
import MealTimeline from "@/components/charts/MealTimeline";

export default function MealPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { data: saved, error, setData: setSaved } = useApi<SavedMeal>(`/meals/${id}`);
  const { data: graph } = useApi<InteractionGraph>("/engine/interactions");
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [analysisErr, setAnalysisErr] = useState<string | null>(null);
  const [fix, setFix] = useState<FixResponse | null>(null);
  const [fixBusy, setFixBusy] = useState(false);
  const [picked, setPicked] = useState<string | null>(null);
  const [accepted, setAccepted] = useState<string | null>(null);
  const [evidence, setEvidence] = useState<string | null>(null);
  const [tab, setTab] = useState<"map" | "waterfall" | "timeline">("map");

  // Analyst agent runs once the meal is loaded.
  const resultKey = saved ? JSON.stringify(saved.result) : null;
  useEffect(() => {
    if (!resultKey) return;
    setAnalysis(null);
    api.post<Analysis>("/agent/analyse", { meal_id: id }).then(setAnalysis).catch((e) => setAnalysisErr(e.message));
  }, [id, resultKey]);

  async function runFix() {
    setFixBusy(true);
    try {
      const f = await api.post<FixResponse>("/agent/fix", { meal_id: id });
      setFix(f);
      setPicked(f.suggestions[0]?.id ?? null);
    } finally {
      setFixBusy(false);
    }
  }

  async function accept() {
    const s = fix?.suggestions.find((x) => x.id === picked);
    if (!s || !saved) return;
    const updated = await api.patch<SavedMeal>(`/meals/${id}`, { change: s.change });
    let msg = `Updated: ${s.title.toLowerCase()}.`;
    if (s.creates_alert) {
      const when = new Date(Date.parse(saved.meal.eaten_at) + s.creates_alert.offset_min * 60000);
      await api.post("/alerts", {
        type: "timing_reminder", meal_id: id, scheduled_for: when.toISOString(),
        message: `You can have your ${s.change.name?.toLowerCase() ?? "drink"} now without affecting ${saved.meal.label?.toLowerCase() ?? "your meal"}.`,
      });
      msg += ` Reminder set for ${time(when.toISOString())}.`;
    }
    setSaved(updated);
    setAccepted(msg);
    setFix(null);
    notifyAlertsChanged();
  }

  if (error) return <p className="text-critical">Couldn't load this meal: {error.message}</p>;
  if (!saved) return <p className="text-muted animate-pulse">Scoring your meal…</p>;
  const { meal, result: r } = saved;
  const gap = r.iron_mg - r.absorbed_mg;

  return (
    <div className="space-y-5">
      <div>
        <div className="text-sm text-ink-2">{meal.label ?? "Meal"} · {time(meal.eaten_at)}</div>
        <h1 className="text-lg font-semibold leading-snug">{[...meal.items, ...meal.drinks].map((i) => i.name).join(", ")}</h1>
      </div>

      {/* Headline: eaten vs absorbed */}
      <section className="grid grid-cols-2 gap-3">
        <div className="card p-4">
          <div className="text-xs text-ink-2">Iron eaten</div>
          <div className="text-3xl font-bold tabular">{mg(r.iron_mg, 1)}</div>
          <div className="text-xs text-muted mt-1">{mg(r.haem_mg, 1)} haem · {mg(r.nonhaem_mg, 1)} non-haem</div>
        </div>
        <div className="card p-4" style={{ borderColor: "var(--series-1)" }}>
          <div className="text-xs text-ink-2">Iron absorbed</div>
          <div className="text-3xl font-bold tabular text-brand">{mg(r.absorbed_mg)}</div>
          <div className="text-xs text-muted mt-1 tabular">{pct(r.fractional_pct)} (range {pct(r.range_pct[0])}–{pct(r.range_pct[1])})</div>
        </div>
      </section>
      <p className="text-sm text-ink-2 -mt-2">Your body gets about {mg(r.absorbed_mg)} of the {mg(r.iron_mg, 1)}. The other {mg(gap, 1)} passes through.</p>

      {/* Conflicts + data gaps */}
      {r.conflicts.map((c) => (
        <div key={c.rule_id} className="card p-3 flex gap-3 items-start" style={{ borderColor: "var(--critical)" }}>
          <span className="text-critical mt-0.5"><IconAlert className="w-5 h-5" /></span>
          <div className="flex-1 text-sm">
            <div className="font-medium">{c.message}</div>
            <button className="text-brand text-xs font-medium mt-1" onClick={() => setEvidence(c.evidence_id)}>See the evidence</button>
          </div>
        </div>
      ))}
      {!!r.data_gaps?.length && (
        <div className="card p-3 text-sm flex gap-3" style={{ borderColor: "var(--warning)" }}>
          <span className="mt-0.5"><IconAlert className="w-5 h-5" /></span>
          Inhibitor data isn&apos;t available for {r.data_gaps.length} item{r.data_gaps.length > 1 ? "s" : ""}, so this estimate may be high.
        </div>
      )}

      {/* Analyst explanation */}
      <section className="card p-4">
        <h2 className="font-semibold mb-2 flex items-center gap-2"><IconSpark className="w-5 h-5 text-brand" />What&apos;s happening</h2>
        {analysis ? (
          <div className="text-sm"><CitedText text={analysis.explanation} citations={analysis.citations} /></div>
        ) : analysisErr ? (
          <p className="text-sm text-muted">Explanation unavailable ({analysisErr}). The numbers above are still correct.</p>
        ) : (
          <p className="text-sm text-muted animate-pulse">Reading the evidence…</p>
        )}
      </section>

      {/* Visuals */}
      <section>
        <div className="grid grid-cols-3 gap-1 p-1 bg-surface-2 rounded-xl mb-3" role="tablist">
          {([["map", "Interactions"], ["waterfall", "Waterfall"], ["timeline", "Timing"]] as const).map(([t, l]) => (
            <button key={t} role="tab" aria-selected={tab === t} onClick={() => setTab(t)} className={`py-2 rounded-lg text-sm font-medium ${tab === t ? "bg-surface shadow-sm" : "text-ink-2"}`}>{l}</button>
          ))}
        </div>
        {tab === "map" && graph && <InteractionMap graph={graph} result={r} height={420} />}
        {tab === "waterfall" && <div className="card p-3"><Waterfall result={r} /></div>}
        {tab === "timeline" && (
          <div className="card p-3">
            <MealTimeline meals={[{ id: meal.id, label: meal.label ?? "Meal", eaten_at: meal.eaten_at, drinks: meal.drinks, window_min: 60 }]}
              startHour={Math.max(0, new Date(meal.eaten_at).getHours() - 3)} endHour={Math.min(24, new Date(meal.eaten_at).getHours() + 4)} />
          </div>
        )}
      </section>

      {/* Fix agent */}
      <section className="card p-4 space-y-3">
        <h2 className="font-semibold">Make this meal work harder</h2>
        {accepted && <p className="text-sm text-good-ink flex gap-2"><IconCheck className="w-5 h-5 shrink-0" />{accepted}</p>}
        {!fix && (
          <button className="btn btn-primary w-full" onClick={runFix} disabled={fixBusy}>
            {fixBusy ? "Testing changes through the engine…" : "Find the smallest fix"}
          </button>
        )}
        {fix && fix.suggestions.length === 0 && <p className="text-sm text-ink-2">No small change improves this meal much. It&apos;s already in good shape.</p>}
        {fix && fix.suggestions.length > 0 && (
          <>
            <BeforeAfter before={r.absorbed_mg} suggestions={fix.suggestions} selectedId={picked} />
            <ul className="space-y-2" role="radiogroup">
              {fix.suggestions.map((s) => (
                <li key={s.id}>
                  <button role="radio" aria-checked={picked === s.id} onClick={() => setPicked(s.id)}
                    className={`w-full text-left rounded-xl border p-3 ${picked === s.id ? "border-brand bg-brand/5" : "border-border"}`}>
                    <div className="flex justify-between gap-2">
                      <span className="font-medium">{s.title}</span>
                      <span className="text-good-ink font-semibold tabular shrink-0">+{mg(s.gain_mg)}</span>
                    </div>
                    <div className="text-xs text-ink-2 mt-0.5">{s.rationale}</div>
                    {s.creates_alert && <div className="text-xs text-brand mt-1 flex items-center gap-1"><IconClock className="w-3.5 h-3.5" />Sets a reminder</div>}
                  </button>
                </li>
              ))}
            </ul>
            <div className="flex gap-3">
              <button className="btn btn-ghost" onClick={() => setFix(null)}>Not now</button>
              <button className="btn btn-primary flex-1" disabled={!picked} onClick={accept}>Accept this change</button>
            </div>
            {fix.fallback_used && <p className="text-[11px] text-muted">Ranked by the deterministic search (agent fallback).</p>}
          </>
        )}
      </section>

      <div className="flex justify-between text-sm">
        <Link href="/today" className="text-brand font-medium">← Today</Link>
        <Link href={`/chat?q=${encodeURIComponent(`Why was my ${meal.label?.toLowerCase() ?? "meal"} so low?`)}`} className="text-brand font-medium">Ask about this meal →</Link>
      </div>
      <p className="text-[11px] text-muted">Estimates from published population-level studies. Not medical advice.</p>
      <EvidenceSheet id={evidence} onClose={() => setEvidence(null)} />
    </div>
  );
}
