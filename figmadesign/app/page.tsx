"use client";
// SCREEN 1: Landing (no nav)
import { motion } from "motion/react";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { Button } from "@/components/ui/primitives";
import { useAuth } from "@/lib/auth";

type N = { x: number; y: number; r: number; label: string; kind: "iron" | "good" | "bad" | "neutral" };
const NODES: N[] = [
  { x: 150, y: 128, r: 40, label: "Iron", kind: "iron" },
  { x: 228, y: 312, r: 32, label: "Iron", kind: "iron" },
  { x: 326, y: 58, r: 29, label: "Vitamin C", kind: "good" },
  { x: 108, y: 254, r: 33, label: "Meat, fish, poultry", kind: "good" },
  { x: 288, y: 150, r: 33, label: "Tea and coffee", kind: "bad" },
  { x: 330, y: 270, r: 28, label: "Phytate", kind: "bad" },
  { x: 54, y: 120, r: 28, label: "Calcium", kind: "bad" },
  { x: 40, y: 206, r: 20, label: "Beans", kind: "neutral" },
  { x: 350, y: 352, r: 19, label: "Lentils", kind: "neutral" },
  { x: 140, y: 340, r: 20, label: "Spinach", kind: "neutral" },
];
const LINKS: [number, number][] = [[6, 0], [0, 2], [2, 4], [0, 3], [3, 7], [7, 6], [3, 9], [9, 1], [1, 5], [4, 5], [1, 8], [5, 8], [4, 1]];
const FILL = { iron: "var(--iron)", good: "color-mix(in oklab, var(--enhancer) 22%, var(--surface))", bad: "color-mix(in oklab, var(--inhibitor) 18%, var(--surface))", neutral: "var(--surface-2)" };
const INK = { iron: "var(--iron-ink)", good: "var(--enhancer)", bad: "var(--inhibitor)", neutral: "var(--muted)" };

function Network() {
  const tea = NODES[4], iron = NODES[0];
  return (
    <div className="grid-paper relative h-[52dvh] max-h-[440px] min-h-[340px] overflow-hidden [mask-image:linear-gradient(to_bottom,black_78%,transparent)]">
      <svg viewBox="0 0 390 400" className="absolute inset-0 h-full w-full" role="img" aria-label="Network of foods that raise or block iron absorption. The link from tea and coffee to iron is highlighted.">
        {LINKS.map(([a, b], i) => (
          <motion.line key={i} x1={NODES[a].x} y1={NODES[a].y} x2={NODES[b].x} y2={NODES[b].y} stroke="var(--faint)" strokeOpacity={0.45} strokeWidth={1.2}
            initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 0.8, delay: 0.2 + i * 0.04 }} />
        ))}
        <motion.line x1={tea.x} y1={tea.y} x2={iron.x} y2={iron.y} stroke="var(--inhibitor)" strokeWidth={16} strokeLinecap="round" style={{ filter: "blur(6px)" }}
          initial={{ opacity: 0 }} animate={{ opacity: [0.1, 0.35, 0.1] }} transition={{ duration: 2.4, repeat: Infinity, delay: 1 }} />
        <motion.line x1={tea.x} y1={tea.y} x2={iron.x} y2={iron.y} stroke="var(--inhibitor)" strokeWidth={4.5} strokeLinecap="round"
          initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 0.9, delay: 0.7 }} />
        {NODES.map((n, i) => (
          <motion.g key={i} initial={{ scale: 0, opacity: 0 }} animate={{ scale: 1, opacity: n.kind === "neutral" ? 0.75 : 1 }}
            transition={{ type: "spring", stiffness: 260, damping: 18, delay: 0.1 + i * 0.06 }} style={{ transformOrigin: `${n.x}px ${n.y}px` }}>
            <motion.g animate={{ y: [0, i % 2 ? 4 : -4, 0] }} transition={{ duration: 5 + (i % 3), repeat: Infinity, ease: "easeInOut" }}>
              {i === 4 && <circle cx={n.x} cy={n.y} r={n.r + 9} fill="var(--inhibitor)" opacity={0.12} />}
              <circle cx={n.x} cy={n.y} r={n.r} fill={i === 4 ? "var(--inhibitor)" : FILL[n.kind]} stroke="var(--surface)" strokeWidth={4} />
              <foreignObject x={n.x - n.r} y={n.y - n.r} width={n.r * 2} height={n.r * 2}>
                <div className="flex h-full w-full items-center justify-center px-1 text-center font-bold leading-[1.05]"
                  style={{ color: i === 4 ? "#fff" : INK[n.kind], fontSize: n.kind === "iron" ? 15 : n.r < 22 ? 8.5 : 9.5 }}>
                  {n.label}
                </div>
              </foreignObject>
            </motion.g>
          </motion.g>
        ))}
      </svg>
      <div className="absolute left-5 top-[max(16px,env(safe-area-inset-top))] text-[25px] font-extrabold tracking-[-0.06em] sm:top-12">avail<span className="text-enhancer">.</span></div>
    </div>
  );
}

export default function Landing() {
  const auth = useAuth();
  const router = useRouter();
  useEffect(() => { if (auth.ready && auth.signedIn) router.replace("/home"); }, [auth.ready, auth.signedIn, router]);
  return (
    <div className="flex min-h-full flex-col">
      <Network />
      <motion.section className="flex flex-1 flex-col px-6 pb-8" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.5, duration: 0.5 }}>
        <h1 className="text-[34px] font-extrabold leading-[1.05] tracking-[-0.03em]">
          What you eat is not what you <span className="text-primary">absorb.</span>
        </h1>
        <p className="mt-4 text-[15px] leading-relaxed text-muted">
          Black tea can cut non-haem iron absorption by 79 to 94%. Avail shows you why, and what to change.
        </p>
        <div className="mt-auto space-y-2 pt-7">
          <Button onClick={auth.login} size="lg" className="w-full">Get started <span aria-hidden>→</span></Button>
          <Button onClick={auth.login} variant="ghost" className="w-full">Sign in</Button>
          {auth.error && <p className="text-center text-sm text-inhibitor">{auth.error}</p>}
          <p className="pt-2 text-center text-[11px] text-faint">Not medical advice. Based on published human studies.</p>
        </div>
      </motion.section>
    </div>
  );
}
