"use client";
// SCREEN 15 (cont.): Alert preferences: toggles per alert type, quiet hours, daily limit.
import { AlertTriangle, Clock3, DatabaseZap, Minus, Plus, Repeat2, TrendingDown } from "lucide-react";
import { BackBar } from "@/components/shell";
import { Card, IconBadge, PageTitle, Switch, cn, type Tone } from "@/components/ui/primitives";
import { useStore, type AlertType } from "@/lib/store";

const TYPES: { t: AlertType; label: string; hint: string; tone: Tone; Icon: typeof Clock3 }[] = [
  { t: "conflict", label: "Meal conflicts", hint: "Right after you log a meal", tone: "red", Icon: AlertTriangle },
  { t: "timing", label: "Timing reminders", hint: "When it's fine to have that drink", tone: "blue", Icon: Clock3 },
  { t: "shortfall", label: "Daily shortfall", hint: "Early evening, if absorbed iron is low", tone: "amber", Icon: TrendingDown },
  { t: "weekly", label: "Weekly patterns", hint: "e.g. tea with lunch 4 times this week", tone: "purple", Icon: Repeat2 },
  { t: "data_gap", label: "Data gaps", hint: "When we couldn't check an item", tone: "grey", Icon: DatabaseZap },
];

export default function AlertPrefs() {
  const prefs = useStore((s) => s.prefs);
  const setPrefs = useStore((s) => s.setPrefs);
  return (
    <div className="space-y-4">
      <BackBar href="/you" />
      <PageTitle eyebrow="You" title="Alert preferences" />
      <Card className="flex items-center justify-between gap-3 p-4">
        <div><p className="font-semibold">All alerts</p><p className="text-sm text-muted">Turn everything off any time</p></div>
        <Switch checked={prefs.enabled} onCheckedChange={(v) => setPrefs({ enabled: v })} label="All alerts" />
      </Card>
      <Card className={cn("divide-y divide-border transition-opacity", !prefs.enabled && "pointer-events-none opacity-45")}>
        {TYPES.map(({ t, label, hint, tone, Icon }) => (
          <div key={t} className="flex min-h-16 items-center gap-3 px-4 py-3">
            <IconBadge tone={tone} size={36}><Icon className="h-[18px] w-[18px]" /></IconBadge>
            <div className="flex-1"><p className="text-sm font-semibold">{label}</p><p className="text-xs text-muted">{hint}</p></div>
            <Switch checked={prefs.types[t]} onCheckedChange={(v) => setPrefs({ types: { ...prefs.types, [t]: v } })} label={label} />
          </div>
        ))}
      </Card>
      <Card className={cn("space-y-4 p-4", !prefs.enabled && "pointer-events-none opacity-45")}>
        <div className="flex items-center justify-between gap-3">
          <div><p className="font-semibold">Quiet hours</p><p className="text-sm text-muted">No notifications in this window</p></div>
          <Switch checked={prefs.quiet.on} onCheckedChange={(v) => setPrefs({ quiet: { ...prefs.quiet, on: v } })} label="Quiet hours" />
        </div>
        {prefs.quiet.on && (
          <div className="grid grid-cols-2 gap-3">
            {(["start", "end"] as const).map((k) => (
              <label key={k} className="text-xs text-muted">{k === "start" ? "From" : "To"}
                <input type="time" value={prefs.quiet[k]} onChange={(e) => setPrefs({ quiet: { ...prefs.quiet, [k]: e.target.value } })} className="mt-1 h-11 w-full rounded-xl border border-border bg-surface px-3 text-sm text-ink" />
              </label>
            ))}
          </div>
        )}
        <div className="flex items-center justify-between border-t border-border pt-4">
          <div><p className="font-semibold">Daily limit</p><p className="text-sm text-muted">At most this many alerts a day</p></div>
          <div className="flex items-center gap-2">
            <button aria-label="Fewer" onClick={() => setPrefs({ daily_limit: Math.max(1, prefs.daily_limit - 1) })} className="grid h-11 w-11 place-items-center rounded-full bg-surface-2"><Minus className="h-4 w-4" /></button>
            <span className="w-6 text-center text-lg font-bold tabular">{prefs.daily_limit}</span>
            <button aria-label="More" onClick={() => setPrefs({ daily_limit: Math.min(8, prefs.daily_limit + 1) })} className="grid h-11 w-11 place-items-center rounded-full bg-surface-2"><Plus className="h-4 w-4" /></button>
          </div>
        </div>
      </Card>
    </div>
  );
}
