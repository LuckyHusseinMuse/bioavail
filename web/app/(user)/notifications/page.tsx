"use client";
// Notification centre: every alert type, mark read / dismiss, link to the meal.
import Link from "next/link";
import type { Alert, AlertType } from "@/lib/types";
import { api, useApi } from "@/lib/api";
import { ago } from "@/lib/format";
import { notifyAlertsChanged } from "@/components/AppShell";
import { IconAlert, IconClock, IconX } from "@/components/Icons";

const ALERT_META: Record<AlertType, { label: string; color: string }> = {
  conflict: { label: "Conflict", color: "var(--critical)" },
  timing_reminder: { label: "Timing reminder", color: "var(--series-1)" },
  daily_shortfall: { label: "Daily shortfall", color: "var(--warning)" },
  weekly_pattern: { label: "Weekly pattern", color: "var(--series-1)" },
  data_gap: { label: "Data gap", color: "var(--warning)" },
};

export default function NotificationsPage() {
  const { data: alerts, setData, loading } = useApi<Alert[]>("/alerts", { refreshMs: 15000 });

  async function mark(a: Alert, body: { read?: boolean; dismissed?: boolean }) {
    setData((xs) => (body.dismissed ? xs?.filter((x) => x.id !== a.id) : xs?.map((x) => (x.id === a.id ? { ...x, read_at: new Date().toISOString() } : x))));
    await api.patch(`/alerts/${a.id}`, body).catch(() => {});
    notifyAlertsChanged();
  }
  const unread = alerts?.filter((a) => !a.read_at) ?? [];

  return (
    <div className="space-y-4">
      <div className="flex items-end justify-between">
        <h1 className="text-2xl font-bold">Notifications</h1>
        <div className="flex gap-3 text-sm">
          {unread.length > 0 && <button className="text-brand font-medium" onClick={() => unread.forEach((a) => mark(a, { read: true }))}>Mark all read</button>}
          <Link href="/settings/alerts" className="text-brand font-medium">Settings</Link>
        </div>
      </div>
      {loading && !alerts && <p className="text-muted animate-pulse">Loading…</p>}
      {alerts?.length === 0 && <div className="card p-6 text-center text-ink-2">No alerts. When a meal has a conflict, you&apos;ll see it here.</div>}
      <ul className="space-y-2">
        {alerts?.map((a) => {
          const meta = ALERT_META[a.type] ?? { label: a.type, color: "var(--muted)" };
          const Icon = a.type === "timing_reminder" ? IconClock : IconAlert;
          return (
            <li key={a.id} className={`card p-3 flex gap-3 ${a.read_at ? "opacity-70" : ""}`}>
              <span className="mt-0.5" style={{ color: meta.color }}><Icon className="w-5 h-5" /></span>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 text-xs text-ink-2">
                  <span className="font-semibold" style={{ color: meta.color === "var(--warning)" ? "var(--text)" : meta.color }}>{meta.label}</span>
                  <span>· {ago(a.sent_at ?? a.created_at)}</span>
                  {!a.read_at && <span className="w-2 h-2 rounded-full bg-brand" aria-label="unread" />}
                </div>
                <p className="text-sm mt-0.5">{a.message}</p>
                <div className="flex gap-4 mt-1.5 text-xs font-medium">
                  {a.meal_id && <Link href={`/meal/${a.meal_id}`} onClick={() => mark(a, { read: true })} className="text-brand">Open meal</Link>}
                  {!a.read_at && <button onClick={() => mark(a, { read: true })} className="text-brand">Mark read</button>}
                </div>
              </div>
              <button onClick={() => mark(a, { dismissed: true })} className="text-muted self-start p-1 -m-1" aria-label="Dismiss"><IconX className="w-4 h-4" /></button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
