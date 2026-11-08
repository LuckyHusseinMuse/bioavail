"use client";
// SCREEN 15: You
import { BellRing, ChevronRight, LayoutGrid, LogOut, Monitor, Moon, RotateCcw, Sun, Trash2 } from "lucide-react";
import { useTheme } from "next-themes";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Card, IconBadge, PageTitle, Segmented, SelectChips } from "@/components/ui/primitives";
import { refIron } from "@/lib/profile";
import { useStore, type Profile } from "@/lib/store";

function LinkRow({ href, icon, title, sub }: { href: string; icon: React.ReactNode; title: string; sub: string }) {
  return (
    <Link href={href} className="flex min-h-16 items-center gap-3 px-4 py-3 hover:bg-surface-2">
      {icon}
      <span className="flex-1"><span className="block font-semibold">{title}</span><span className="text-sm text-muted">{sub}</span></span>
      <ChevronRight className="h-5 w-5 text-faint" />
    </Link>
  );
}

export default function YouPage() {
  const router = useRouter();
  const profile = useStore((s) => s.profile);
  const setProfile = useStore((s) => s.setProfile);
  const reminders = useStore((s) => s.reminders);
  const prefs = useStore((s) => s.prefs);
  const resetDemo = useStore((s) => s.resetDemo);
  const clearAll = useStore((s) => s.clearAll);
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  const set = <K extends keyof Profile>(k: K) => (v: Profile[K]) => { setProfile({ [k]: v } as Partial<Profile>); toast.success("Profile updated"); };

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-4 pt-1">
        <span className="grid h-16 w-16 place-items-center rounded-full bg-primary text-2xl font-extrabold text-primary-ink">{profile.name[0]}</span>
        <PageTitle eyebrow="Your profile" title={profile.name} />
      </div>

      <Card className="space-y-5 p-5">
        <SelectChips label="Age band" value={profile.age_band} onChange={set("age_band")} options={["under 19", "19-50", "51+"]} />
        <SelectChips label="Sex" value={profile.sex} onChange={set("sex")} options={["Female", "Male", "Prefer not to say"]} />
        <SelectChips label="Diet type" value={profile.diet} onChange={set("diet")} options={["Omnivore", "Pescatarian", "Vegetarian", "Vegan"]} />
        <p className="rounded-xl bg-primary/8 p-3 text-sm">Your daily iron reference: <strong className="tabular">{refIron(profile)} mg</strong> <span className="text-muted">(UK government)</span></p>
      </Card>

      <Card className="divide-y divide-border overflow-hidden">
        <LinkRow href="/you/reminders" icon={<IconBadge tone="blue"><BellRing className="h-5 w-5" /></IconBadge>} title="Reminders" sub={`${reminders.length} set · supplements and drinks`} />
        <LinkRow href="/you/alerts" icon={<IconBadge tone="amber"><BellRing className="h-5 w-5" /></IconBadge>} title="Alert preferences" sub={prefs.enabled ? `${Object.values(prefs.types).filter(Boolean).length} types on · max ${prefs.daily_limit} a day` : "All alerts off"} />
      </Card>

      <Card className="p-5">
        <p className="mb-3 text-sm font-semibold">Appearance</p>
        {mounted && (
          <Segmented id="theme" value={(theme ?? "system") as "light" | "dark" | "system"} onChange={(v) => setTheme(v)} options={[
            { value: "light", label: <span className="flex items-center justify-center gap-1.5"><Sun className="h-4 w-4" />Light</span> },
            { value: "dark", label: <span className="flex items-center justify-center gap-1.5"><Moon className="h-4 w-4" />Dark</span> },
            { value: "system", label: <span className="flex items-center justify-center gap-1.5"><Monitor className="h-4 w-4" />System</span> },
          ]} />
        )}
      </Card>

      <Card className="divide-y divide-border overflow-hidden">
        <LinkRow href="/screens" icon={<IconBadge tone="green"><LayoutGrid className="h-5 w-5" /></IconBadge>} title="Prototype map" sub="Jump to any of the 17 screens" />
        <button onClick={() => { resetDemo(); toast.success("Demo data restored"); }} className="flex min-h-14 w-full items-center gap-3 px-4 text-left font-semibold hover:bg-surface-2"><RotateCcw className="h-5 w-5 text-muted" />Reset demo data</button>
        <button onClick={() => { clearAll(); toast("All meals and alerts cleared", { description: "See the empty states in History and Notifications." }); }} className="flex min-h-14 w-full items-center gap-3 px-4 text-left font-semibold hover:bg-surface-2"><Trash2 className="h-5 w-5 text-muted" />Clear all data</button>
        <button onClick={() => router.push("/")} className="flex min-h-14 w-full items-center gap-3 px-4 text-left font-semibold text-inhibitor hover:bg-surface-2"><LogOut className="h-5 w-5" />Sign out</button>
      </Card>
      <p className="text-center text-[11px] text-faint">Avail supports healthier eating. It does not diagnose or treat iron deficiency.</p>
    </div>
  );
}
