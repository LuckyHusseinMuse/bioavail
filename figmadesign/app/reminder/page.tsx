"use client";
// SCREEN 16: Supplement reminder
import * as ToggleGroup from "@radix-ui/react-toggle-group";
import { CalendarPlus, CheckCircle2, Sparkles } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { BackBar } from "@/components/shell";
import { Button, Card, PageTitle, Segmented, Switch } from "@/components/ui/primitives";
import { icsFor, suggestSupplementTime } from "@/lib/logic";
import { isToday, useStore } from "@/lib/store";

const DAYS = [["MO", "M"], ["TU", "T"], ["WE", "W"], ["TH", "T"], ["FR", "F"], ["SA", "S"], ["SU", "S"]] as const;

export default function SupplementReminder() {
  const router = useRouter();
  const meals = useStore((s) => s.meals);
  const addReminder = useStore((s) => s.addReminder);
  const [what, setWhat] = useState("");
  const [time, setTime] = useState("10:30");
  const [repeat, setRepeat] = useState<"daily" | "alternate" | "days">("daily");
  const [days, setDays] = useState<string[]>(["MO", "WE", "FR"]);
  const [suggestion, setSuggestion] = useState<string | null>(null);
  const [notify, setNotify] = useState(typeof Notification !== "undefined" && Notification.permission === "granted");
  const title = what.trim() || "Iron tablet";

  function suggest() {
    const s = suggestSupplementTime(meals.filter((m) => isToday(m.eaten_at)));
    if (s) { setTime(s.time); setSuggestion(`You have no tea, coffee or dairy logged between ${s.window}.`); }
    else setSuggestion("Tea, coffee or dairy are logged across most of today. Try mid-morning, away from meals.");
  }

  function toggleNotify(v: boolean) {
    if (v && (typeof Notification === "undefined" || Notification.permission !== "granted")) { router.push("/permission?next=/reminder"); return; }
    setNotify(v);
  }

  function calendar() {
    const blob = new Blob([icsFor(`Take ${title.toLowerCase()}`, time, repeat, days)], { type: "text/calendar" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "avail-supplement-reminder.ics";
    a.click();
    URL.revokeObjectURL(a.href);
  }

  function save() {
    addReminder({ kind: "supplement", title, time, repeat, days, notify });
    toast.success(`Reminder set for ${time}`);
    router.push("/you/reminders");
  }

  return (
    <div className="space-y-4">
      <BackBar />
      <PageTitle eyebrow="Reminders" title="Supplement reminder" />
      <Card className="space-y-5 p-5">
        <label className="block">
          <span className="text-sm font-semibold">What are you taking?</span>
          <input value={what} onChange={(e) => setWhat(e.target.value)} placeholder="Iron tablet" className="mt-2 h-12 w-full rounded-xl border border-border bg-surface px-4 outline-none placeholder:text-faint focus:border-primary" />
        </label>
        <label className="flex items-center justify-between">
          <span className="text-sm font-semibold">Time</span>
          <input type="time" value={time} onChange={(e) => setTime(e.target.value)} className="h-12 rounded-xl border border-border bg-surface px-4 text-lg font-bold tabular" />
        </label>
        <div className="space-y-2">
          <span className="text-sm font-semibold">Repeat</span>
          <Segmented id="repeat" size="sm" value={repeat} onChange={setRepeat} options={[{ value: "daily", label: "Every day" }, { value: "alternate", label: "Every other day" }, { value: "days", label: "Choose days" }]} />
          <AnimatePresence>
            {repeat === "days" && (
              <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }}>
                <ToggleGroup.Root type="multiple" value={days} onValueChange={setDays} className="flex justify-between pt-2">
                  {DAYS.map(([v, l]) => (
                    <ToggleGroup.Item key={v} value={v} aria-label={v} className="grid h-11 w-11 place-items-center rounded-full border border-border text-sm font-bold text-muted data-[state=on]:border-primary data-[state=on]:bg-primary data-[state=on]:text-primary-ink">{l}</ToggleGroup.Item>
                  ))}
                </ToggleGroup.Root>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
        <div>
          <Button variant="secondary" className="w-full" onClick={suggest}><Sparkles className="h-4 w-4" />Suggest a time</Button>
          <AnimatePresence>
            {suggestion && (
              <motion.p initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} className="mt-2 flex gap-2 rounded-xl bg-enhancer/12 p-3 text-sm">
                <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-enhancer" />{suggestion}
              </motion.p>
            )}
          </AnimatePresence>
        </div>
        <div className="flex items-center justify-between border-t border-border pt-4">
          <span className="text-sm font-semibold">Notify me on this phone</span>
          <Switch checked={notify} onCheckedChange={toggleNotify} label="Notify me on this phone" />
        </div>
        <button onClick={calendar} className="flex min-h-11 items-center gap-1.5 text-sm font-bold text-primary"><CalendarPlus className="h-4 w-4" />Add to calendar instead</button>
      </Card>
      <Button size="lg" className="w-full" onClick={save}>Save reminder</Button>
      <p className="px-2 text-center text-[11px] text-faint">Avail doesn&apos;t advise whether or how much to take. Ask your GP or pharmacist.</p>
    </div>
  );
}
