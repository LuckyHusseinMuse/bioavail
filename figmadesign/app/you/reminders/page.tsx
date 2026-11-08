"use client";
import { AlarmClock, CupSoda, Pill, Plus, Trash2 } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { BackBar } from "@/components/shell";
import { Button, Card, EmptyState, IconBadge, PageTitle } from "@/components/ui/primitives";
import { useStore } from "@/lib/store";

const REPEAT = { once: "Once", daily: "Every day", alternate: "Every other day", days: "Chosen days" };

export default function Reminders() {
  const reminders = useStore((s) => s.reminders);
  const remove = useStore((s) => s.removeReminder);
  return (
    <div className="space-y-4">
      <BackBar href="/you" />
      <PageTitle eyebrow="You" title="Reminders" />
      {reminders.length ? (
        <Card className="divide-y divide-border">
          <AnimatePresence initial={false}>
            {reminders.map((r) => (
              <motion.div key={r.id} layout exit={{ opacity: 0, height: 0 }} className="flex min-h-16 items-center gap-3 px-4 py-3">
                <IconBadge tone={r.kind === "supplement" ? "purple" : "blue"}>{r.kind === "supplement" ? <Pill className="h-5 w-5" /> : <CupSoda className="h-5 w-5" />}</IconBadge>
                <div className="flex-1"><p className="font-semibold">{r.title}</p><p className="text-sm text-muted tabular">{r.time} · {REPEAT[r.repeat]}{r.repeat === "days" ? ` (${r.days.join(", ")})` : ""}</p></div>
                <button onClick={() => remove(r.id)} aria-label={`Delete ${r.title}`} className="grid h-11 w-11 place-items-center rounded-xl text-muted hover:bg-surface-2"><Trash2 className="h-[18px] w-[18px]" /></button>
              </motion.div>
            ))}
          </AnimatePresence>
        </Card>
      ) : (
        <EmptyState icon={<AlarmClock className="h-7 w-7" />} title="No reminders yet" body="Set one from a fix suggestion, or for a supplement." />
      )}
      <Button href="/reminder" size="lg" className="w-full"><Plus className="h-5 w-5" />New supplement reminder</Button>
    </div>
  );
}
