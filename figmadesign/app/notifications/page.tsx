"use client";
// SCREEN 14: Notifications (opened from the bell). Swipe a card left to dismiss.
import { AlertTriangle, BellOff, Clock3, DatabaseZap, Repeat2, Settings, TrendingDown } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { EmptyState, IconBadge, PageTitle, cn, type Tone } from "@/components/ui/primitives";
import { isToday, useStore, type Alert, type AlertType } from "@/lib/store";

const META: Record<AlertType, { label: string; tone: Tone; Icon: typeof AlertTriangle }> = {
  conflict: { label: "Meal conflict", tone: "red", Icon: AlertTriangle },
  timing: { label: "Timing reminder", tone: "blue", Icon: Clock3 },
  shortfall: { label: "Daily check-in", tone: "amber", Icon: TrendingDown },
  weekly: { label: "Weekly pattern", tone: "purple", Icon: Repeat2 },
  data_gap: { label: "Data gap", tone: "grey", Icon: DatabaseZap },
};

const ago = (iso: string) => {
  const s = (Date.now() - Date.parse(iso)) / 1000;
  if (s < 0) return new Date(iso).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
  if (s < 60) return "Just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  return new Date(iso).toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" });
};

function Row({ a }: { a: Alert }) {
  const router = useRouter();
  const markRead = useStore((s) => s.markRead);
  const dismiss = useStore((s) => s.dismissAlert);
  const setCurrent = useStore((s) => s.setCurrentMeal);
  const { label, tone, Icon } = META[a.type];
  const [dragging, setDragging] = useState(false);
  return (
    <motion.li layout exit={{ opacity: 0, x: -320, height: 0, marginBottom: 0 }} transition={{ duration: 0.25 }} className="relative mb-2.5 overflow-hidden rounded-2xl">
      {dragging && <div className="absolute inset-0 flex items-center justify-end rounded-2xl bg-inhibitor pr-5 text-sm font-bold text-white">Dismiss</div>}
      <motion.button drag="x" dragConstraints={{ left: 0, right: 0 }} dragElastic={{ left: 0.6, right: 0 }}
        onDragStart={() => setDragging(true)}
        onDragEnd={(_, i) => { setDragging(false); if (i.offset.x < -110) dismiss(a.id); }}
        onClick={() => { markRead(a.id); if (a.meal_id) { setCurrent(a.meal_id); router.push(a.type === "conflict" ? "/fix" : "/absorb"); } }}
        className={cn("relative flex w-full items-start gap-3 rounded-2xl border border-border bg-surface p-4 text-left shadow-card", a.read && "[&_p]:text-muted")}>
        <IconBadge tone={tone}><Icon className="h-5 w-5" /></IconBadge>
        <div className="min-w-0 flex-1">
          <p className="flex items-center gap-2 text-[11px] font-bold uppercase tracking-[0.06em] text-faint">{label}<span className="font-medium normal-case tracking-normal">· {ago(a.created_at)}</span></p>
          <p className="mt-0.5 font-semibold leading-snug">{a.title}</p>
          <p className="mt-0.5 text-sm text-muted">{a.detail}</p>
        </div>
        {!a.read && <span className="mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full bg-primary" aria-label="Unread" />}
      </motion.button>
    </motion.li>
  );
}

export default function NotificationsPage() {
  const alerts = useStore((s) => s.alerts);
  const markAll = useStore((s) => s.markAllRead);
  const sorted = [...alerts].sort((a, b) => b.created_at.localeCompare(a.created_at));
  const today = sorted.filter((a) => isToday(a.created_at));
  const earlier = sorted.filter((a) => !isToday(a.created_at));

  return (
    <div className="space-y-4">
      <PageTitle eyebrow="Your updates" title="Notifications"
        right={<Link href="/you/alerts" aria-label="Alert preferences" className="grid h-11 w-11 place-items-center rounded-full border border-border bg-surface"><Settings className="h-5 w-5" /></Link>} />
      {alerts.some((a) => !a.read) && <button onClick={markAll} className="min-h-9 text-sm font-bold text-primary">Mark all read</button>}
      {!alerts.length && <EmptyState icon={<BellOff className="h-7 w-7" />} title="No alerts yet" body="When a meal has a conflict, you'll see it here." />}
      {[["Today", today], ["Earlier", earlier]].map(([title, list]) =>
        (list as Alert[]).length ? (
          <section key={title as string}>
            <p className="mb-2 text-xs font-bold uppercase tracking-[0.08em] text-faint">{title as string}</p>
            <ul><AnimatePresence initial={false}>{(list as Alert[]).map((a) => <Row key={a.id} a={a} />)}</AnimatePresence></ul>
          </section>
        ) : null,
      )}
      {alerts.length > 0 && <p className="text-center text-xs text-faint">Swipe left to dismiss</p>}
    </div>
  );
}
