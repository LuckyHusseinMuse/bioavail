"use client";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import type { Profile } from "@/lib/types";
import { api, useApi } from "@/lib/api";
import FoodSearch from "@/components/FoodSearch";
import { IconX } from "@/components/Icons";

type InstallEvent = Event & { prompt: () => Promise<void>; userChoice: Promise<{ outcome: string }> };

function Choice<T extends string>({ label, value, options, onChange }: { label: string; value: T | null; options: { v: T; l: string }[]; onChange: (v: T) => void }) {
  return (
    <fieldset>
      <legend className="text-sm font-medium mb-2">{label}</legend>
      <div className="flex flex-wrap gap-2">
        {options.map((o) => (
          <button type="button" key={o.v} onClick={() => onChange(o.v)} aria-pressed={value === o.v}
            className={`px-3 py-2 rounded-xl border text-sm ${value === o.v ? "border-brand bg-brand/10 font-semibold" : "border-border bg-surface"}`}>{o.l}</button>
        ))}
      </div>
    </fieldset>
  );
}

function ProfileInner() {
  const onboarding = useSearchParams().get("onboarding") === "1";
  const { data, setData } = useApi<Profile>("/me/profile");
  const [draft, setDraft] = useState<Profile | null>(null);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [picking, setPicking] = useState(false);
  const [install, setInstall] = useState<InstallEvent | null>(null);
  const [standalone, setStandalone] = useState(false);

  useEffect(() => { if (data && !draft) setDraft(data); }, [data, draft]);
  useEffect(() => {
    setStandalone(window.matchMedia("(display-mode: standalone)").matches);
    const h = (e: Event) => { e.preventDefault(); setInstall(e as InstallEvent); };
    window.addEventListener("beforeinstallprompt", h);
    return () => window.removeEventListener("beforeinstallprompt", h);
  }, []);

  if (!draft) return <p className="text-muted animate-pulse">Loading…</p>;
  const dirty = JSON.stringify(draft) !== JSON.stringify(data);
  const set = (p: Partial<Profile>) => setDraft({ ...draft, ...p });

  async function save() {
    setSaving(true);
    try {
      const p = await api.put<Profile>("/me/profile", draft);
      setData(p); setDraft(p); setMsg("Profile saved");
    } catch (e) { setMsg((e as Error).message); }
    setSaving(false);
  }

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-bold">{onboarding ? "Set up your profile" : "Profile"}</h1>
        <p className="text-sm text-ink-2">{draft.name ?? draft.email}</p>
      </div>

      <section className="card p-4 space-y-5">
        <Choice label="Sex (sets your daily iron reference)" value={draft.sex} onChange={(v) => set({ sex: v })}
          options={[{ v: "female", l: "Female" }, { v: "male", l: "Male" }, { v: "other", l: "Prefer not to say" }]} />
        <Choice label="Age" value={draft.age_band} onChange={(v) => set({ age_band: v })}
          options={[{ v: "19-50", l: "19 to 50" }, { v: "51+", l: "51+" }]} />
        <Choice label="Diet" value={draft.diet_type} onChange={(v) => set({ diet_type: v })}
          options={[{ v: "omnivore", l: "Everything" }, { v: "pescatarian", l: "Pescatarian" }, { v: "vegetarian", l: "Vegetarian" }, { v: "vegan", l: "Vegan" }]} />
        <div className="rounded-xl bg-surface-2 p-3 text-sm">
          Your reference intake: <strong className="tabular">{data?.reference_iron_mg} mg</strong> iron a day <span className="text-ink-2">(UK government, updates when you save)</span>
        </div>
      </section>

      <section className="card p-4 space-y-3">
        <div className="text-sm font-medium">Foods to never suggest</div>
        <div className="flex flex-wrap gap-2">
          {draft.preferences.avoid.map((code) => (
            <span key={code} className="flex items-center gap-1 pl-3 pr-1 py-1 rounded-full bg-surface-2 text-sm">
              {code.replace(/^MOCK_/, "").toLowerCase().replace(/_/g, " ")}
              <button onClick={() => set({ preferences: { ...draft.preferences, avoid: draft.preferences.avoid.filter((x) => x !== code) } })} aria-label="Remove" className="p-1"><IconX className="w-3.5 h-3.5" /></button>
            </span>
          ))}
          {!picking && <button onClick={() => setPicking(true)} className="text-sm text-brand font-medium px-2">+ Add</button>}
        </div>
        {picking && <FoodSearch onPick={(f) => { set({ preferences: { ...draft.preferences, avoid: [...new Set([...draft.preferences.avoid, f.food_code])] } }); setPicking(false); }} />}
      </section>

      {msg && <p className="text-sm text-brand" role="status">{msg}</p>}
      <button className="btn btn-primary w-full" disabled={!dirty || saving} onClick={save}>{saving ? "Saving…" : dirty ? "Save changes" : "Saved"}</button>

      <section className="card divide-y divide-border">
        <Link href="/settings/alerts" className="block p-4">Alert settings →</Link>
        <Link href="/notifications" className="block p-4">Notifications →</Link>
        <Link href="/validation" className="block p-4">How accurate is Absorb? →</Link>
        {!standalone && (
          install ? (
            <button className="block p-4 w-full text-left text-brand font-medium" onClick={async () => { await install.prompt(); setInstall(null); }}>Install the app</button>
          ) : (
            <p className="p-4 text-sm text-ink-2">To install: on iPhone tap Share → Add to Home Screen. On Android use the browser menu → Install app.</p>
          )
        )}
        <a href="/auth/logout" className="block p-4 text-critical">Sign out</a>
      </section>
      <p className="text-[11px] text-muted">Absorb supports healthier eating. It does not diagnose or treat iron deficiency. If you have symptoms, see a GP.</p>
    </div>
  );
}

export default function ProfilePage() {
  return <Suspense><ProfileInner /></Suspense>;
}
