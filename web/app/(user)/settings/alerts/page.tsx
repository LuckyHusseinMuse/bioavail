"use client";
// Alert preferences: master switch, per-type toggles, quiet hours, daily limit, shortfall time,
// and the Web Push subscription (sent to the backend inside preferences).
import { useEffect, useState } from "react";
import type { AlertPreferences, AlertType } from "@/lib/types";
import { api, useApi } from "@/lib/api";
import { pushSupport, showLocalNotification, subscribeToPush, unsubscribeFromPush } from "@/lib/push";

const TYPES: { t: AlertType; label: string; hint: string }[] = [
  { t: "conflict", label: "Conflict alerts", hint: "Right after you log a meal with a conflict" },
  { t: "timing_reminder", label: "Timing reminders", hint: "When it's OK to have the drink you moved" },
  { t: "daily_shortfall", label: "Daily shortfall", hint: "Early evening, if absorbed iron is low" },
  { t: "weekly_pattern", label: "Weekly patterns", hint: "e.g. tea with 4 of 5 lunches" },
  { t: "data_gap", label: "Data gaps", hint: "When we can't check a food for inhibitors" },
];

function Toggle({ on, onChange, label }: { on: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <button role="switch" aria-checked={on} aria-label={label} onClick={() => onChange(!on)}
      className={`w-12 h-7 rounded-full relative transition-colors shrink-0 ${on ? "bg-brand" : "bg-surface-2 border border-border"}`}>
      <span className={`absolute top-0.5 w-6 h-6 rounded-full bg-white shadow transition-all ${on ? "left-[22px]" : "left-0.5"}`} />
    </button>
  );
}

export default function AlertSettings() {
  const { data, setData } = useApi<AlertPreferences>("/alerts/preferences");
  const [status, setStatus] = useState<string | null>(null);
  const [support, setSupport] = useState<{ supported: boolean; reason?: string }>({ supported: false });
  useEffect(() => setSupport(pushSupport()), []);

  async function save(patch: Partial<AlertPreferences>) {
    if (!data) return;
    const next = { ...data, ...patch };
    setData(next);
    try { setData(await api.put<AlertPreferences>("/alerts/preferences", next)); setStatus("Saved"); }
    catch (e) { setStatus(`Couldn't save: ${(e as Error).message}`); }
    setTimeout(() => setStatus(null), 2000);
  }

  async function enablePush() {
    try {
      const sub = await subscribeToPush();
      await save({ push_subscription: sub });
      setStatus("Push notifications on");
    } catch (e) {
      setStatus((e as Error).message);
    }
  }
  async function disablePush() {
    await unsubscribeFromPush();
    await save({ push_subscription: null });
  }

  if (!data) return <p className="text-muted animate-pulse">Loading…</p>;
  const toggleType = (t: AlertType, on: boolean) =>
    save({ enabled_types: on ? [...new Set([...data.enabled_types, t])] : data.enabled_types.filter((x) => x !== t) });

  return (
    <div className="space-y-5">
      <h1 className="text-2xl font-bold">Alert settings</h1>
      {status && <p className="text-sm text-brand" role="status">{status}</p>}

      <section className="card p-4 flex items-center justify-between gap-3">
        <div><div className="font-medium">Alerts</div><div className="text-xs text-ink-2">Turn every alert off or on</div></div>
        <Toggle on={data.enabled} onChange={(v) => save({ enabled: v })} label="All alerts" />
      </section>

      <section className={`card divide-y divide-border ${data.enabled ? "" : "opacity-50 pointer-events-none"}`}>
        {TYPES.map(({ t, label, hint }) => (
          <div key={t} className="p-4 flex items-center justify-between gap-3">
            <div><div className="font-medium text-sm">{label}</div><div className="text-xs text-ink-2">{hint}</div></div>
            <Toggle on={data.enabled_types.includes(t)} onChange={(v) => toggleType(t, v)} label={label} />
          </div>
        ))}
      </section>

      <section className={`card p-4 space-y-4 ${data.enabled ? "" : "opacity-50 pointer-events-none"}`}>
        <div className="flex items-center justify-between gap-3">
          <div><div className="font-medium text-sm">Quiet hours</div><div className="text-xs text-ink-2">No push notifications in this window</div></div>
          <Toggle on={!!data.quiet_hours} onChange={(v) => save({ quiet_hours: v ? { start: "22:00", end: "07:30" } : null })} label="Quiet hours" />
        </div>
        {data.quiet_hours && (
          <div className="flex gap-3">
            <label className="flex-1 text-xs text-ink-2">From<input type="time" className="input mt-1" value={data.quiet_hours.start} onChange={(e) => save({ quiet_hours: { ...data.quiet_hours!, start: e.target.value } })} /></label>
            <label className="flex-1 text-xs text-ink-2">To<input type="time" className="input mt-1" value={data.quiet_hours.end} onChange={(e) => save({ quiet_hours: { ...data.quiet_hours!, end: e.target.value } })} /></label>
          </div>
        )}
        <label className="block text-sm">
          <span className="font-medium">At most {data.daily_limit} alert{data.daily_limit === 1 ? "" : "s"} a day</span>
          <input type="range" min={1} max={6} value={data.daily_limit} onChange={(e) => save({ daily_limit: Number(e.target.value) })} className="w-full mt-2 accent-[var(--brand)]" />
        </label>
        <label className="block text-xs text-ink-2">Daily shortfall check at
          <input type="time" className="input mt-1" value={data.shortfall_time} onChange={(e) => save({ shortfall_time: e.target.value })} />
        </label>
      </section>

      <section className="card p-4 space-y-3">
        <div className="font-medium">Push notifications</div>
        {!support.supported ? (
          <p className="text-sm text-ink-2">{support.reason ?? "Checking…"} Alerts still appear in the notification centre.</p>
        ) : data.push_subscription ? (
          <>
            <p className="text-sm text-good-ink">✓ This device receives push notifications.</p>
            <div className="flex gap-2">
              <button className="btn btn-ghost flex-1" onClick={() => showLocalNotification("Absorb", "Test: notifications are working.")}>Send a test</button>
              <button className="btn btn-ghost flex-1" onClick={disablePush}>Turn off</button>
            </div>
          </>
        ) : (
          <button className="btn btn-primary w-full" onClick={enablePush}>Enable push on this device</button>
        )}
      </section>
    </div>
  );
}
