"use client";
// SCREEN 4: Analysing. Animated steps, then on to Confirm.
import { Check, Loader2 } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useStore } from "@/lib/store";

const STEPS = ["Identifying foods", "Matching to the food table", "Checking portions"];

export default function Analysing() {
  const router = useRouter();
  const photo = useStore((s) => s.draft?.photo);
  const [done, setDone] = useState(0);

  useEffect(() => {
    const ts = STEPS.map((_, i) => setTimeout(() => setDone(i + 1), 900 * (i + 1)));
    const go = setTimeout(() => router.replace("/confirm"), 900 * STEPS.length + 500);
    return () => { ts.forEach(clearTimeout); clearTimeout(go); };
  }, [router]);

  return (
    <div className="flex min-h-[70dvh] flex-col items-center justify-center text-center sm:min-h-[640px]">
      <div className="relative h-36 w-36">
        <motion.div className="absolute inset-0 rounded-full border-4 border-primary/15" />
        <motion.div className="absolute inset-0 rounded-full border-4 border-transparent border-t-primary" animate={{ rotate: 360 }} transition={{ duration: 1.1, repeat: Infinity, ease: "linear" }} />
        <div className="absolute inset-3 overflow-hidden rounded-full bg-surface-2">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          {photo ? <img src={photo} alt="" className="h-full w-full object-cover" /> : <div className="grid h-full place-items-center text-3xl font-extrabold text-primary">Fe</div>}
          <motion.div className="absolute inset-x-0 h-8 bg-gradient-to-b from-transparent via-white/40 to-transparent" animate={{ y: [-40, 140] }} transition={{ duration: 1.6, repeat: Infinity, ease: "easeInOut" }} />
        </div>
      </div>
      <h1 className="mt-8 text-2xl font-extrabold tracking-tight">Analysing your meal</h1>
      <p className="mt-1 text-sm text-muted">This takes a few seconds</p>
      <ul className="mt-8 w-full max-w-[280px] space-y-3 text-left">
        {STEPS.map((s, i) => {
          const state = i < done ? "done" : i === done ? "active" : "todo";
          return (
            <motion.li key={s} initial={{ opacity: 0, x: -8 }} animate={{ opacity: state === "todo" ? 0.45 : 1, x: 0 }} transition={{ delay: i * 0.12 }}
              className="flex items-center gap-3 rounded-2xl bg-surface p-3 shadow-card">
              <span className={`grid h-8 w-8 place-items-center rounded-full ${state === "done" ? "bg-enhancer text-white" : "bg-surface-2 text-primary"}`}>
                <AnimatePresence mode="wait">
                  {state === "done" ? (
                    <motion.span key="d" initial={{ scale: 0 }} animate={{ scale: 1 }}><Check className="h-4 w-4" /></motion.span>
                  ) : state === "active" ? <Loader2 key="a" className="h-4 w-4 animate-spin" /> : <span key="t" className="text-xs font-bold">{i + 1}</span>}
                </AnimatePresence>
              </span>
              <span className="text-sm font-semibold">{s}</span>
            </motion.li>
          );
        })}
      </ul>
    </div>
  );
}
