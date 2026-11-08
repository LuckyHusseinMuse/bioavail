"use client";
// Prototype map: every screen and state from the design brief, one tap away.
import { ArrowUpRight } from "lucide-react";
import { motion } from "motion/react";
import Link from "next/link";
import { useStore } from "@/lib/store";

const SCREENS: [number, string, string, string?][] = [
  [1, "Landing", "/"],
  [2, "Home", "/home"],
  [3, "Add meal: Add image", "/add"],
  [3, "Add meal: Description", "/add?tab=description"],
  [3, "Add meal: Search item", "/add?tab=search"],
  [4, "Analysing", "/analysing"],
  [5, "Confirm your meal", "/confirm?state=demo"],
  [5, "Confirm: photo error", "/confirm?state=error"],
  [6, "Absorb: Breakdown", "/absorb"],
  [7, "Absorb: Map", "/absorb?tab=map"],
  [8, "Absorb: Evidence", "/absorb?tab=evidence"],
  [9, "Evidence sheet", "/absorb", "Tap “See source” or a citation chip"],
  [10, "Fix suggestions", "/fix"],
  [11, "Conflict toast", "/absorb?toast=1"],
  [12, "Chat", "/chat?demo=1"],
  [12, "Chat: refusal", "/chat?demo=refusal"],
  [13, "History", "/history"],
  [14, "Notifications", "/notifications"],
  [15, "You", "/you"],
  [15, "Alert preferences", "/you/alerts"],
  [16, "Supplement reminder", "/reminder"],
  [17, "Permission priming", "/permission?next=/screens"],
];

export default function ScreensPage() {
  const lunch = useStore((s) => s.meals.findLast((m) => m.drinks.some((d) => d.food_code === "MOCK_BLACK_TEA")));
  const setCurrent = useStore((s) => s.setCurrentMeal);
  return (
    <div className="px-5 pb-10 pt-14">
      <p className="text-[11px] font-bold uppercase tracking-[0.08em] text-primary">Prototype map</p>
      <h1 className="mt-1 text-[26px] font-extrabold tracking-tight">All screens</h1>
      <p className="mt-1 text-sm text-muted">Empty states: You → Clear all data. Restore with Reset demo data.</p>
      <ul className="mt-5 space-y-2">
        {SCREENS.map(([n, name, href, hint], i) => (
          <motion.li key={href + name} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.02 }}>
            <Link href={href} onClick={() => href.startsWith("/absorb") || href.startsWith("/fix") ? lunch && setCurrent(lunch.id) : undefined}
              className="flex min-h-14 items-center gap-3 rounded-2xl border border-border bg-surface px-4 py-2.5 shadow-card">
              <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-primary/10 text-xs font-bold text-primary tabular">{n}</span>
              <span className="flex-1"><span className="block text-sm font-semibold">{name}</span>{hint && <span className="text-xs text-muted">{hint}</span>}</span>
              <ArrowUpRight className="h-4 w-4 text-faint" />
            </Link>
          </motion.li>
        ))}
      </ul>
    </div>
  );
}
