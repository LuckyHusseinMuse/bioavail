"use client";
// "What changed your absorption": Base % → one row per factor (×multiplier) → Final %.
// Red rows lower absorption, grey rows had no effect (already counted in the base), green raise it.
import type { EngineResult } from "@/lib/engine/types";
import { Bar } from "../ui/primitives";

const NAME: Record<string, string> = { polyphenols: "Polyphenols", phytate: "Phytate", calcium: "Calcium", vitamin_c: "Vitamin C", mfp: "Meat, fish, poultry", floor: "Minimum floor" };

export function waterfall(r: EngineResult) {
  let cur = r.base_pct;
  const rows: { label: string; value: string; pct: number; tone: "base" | "down" | "flat" | "up" | "final" }[] = [{ label: "Base", value: `${r.base_pct}%`, pct: cur, tone: "base" }];
  for (const c of r.contributions) {
    cur = cur * c.multiplier;
    rows.push({ label: NAME[c.factor] ?? c.factor, value: `×${c.multiplier === 1 ? "1.0" : c.multiplier}`, pct: cur, tone: c.multiplier < 1 ? "down" : c.multiplier > 1 ? "up" : "flat" });
  }
  rows.push({ label: "Final", value: `${cur < 1 ? cur.toFixed(2) : cur.toFixed(1)}%`, pct: cur, tone: "final" });
  return rows;
}

const COLOR = { base: "var(--primary)", final: "var(--primary)", down: "var(--inhibitor)", up: "var(--enhancer)", flat: "var(--faint)" };

export default function Waterfall({ result }: { result: EngineResult }) {
  const rows = waterfall(result);
  const max = Math.max(...rows.map((r) => r.pct));
  return (
    <div className="space-y-3" role="table" aria-label="How each factor changed non-haem iron absorption">
      {rows.map((r, i) => (
        <div key={r.label + i} role="row" className="flex items-center gap-3">
          <span role="cell" className="w-[104px] shrink-0 text-[13px] font-semibold">{r.label}</span>
          <Bar pct={(r.pct / max) * 100} color={COLOR[r.tone]} delay={i * 0.12} />
          <strong role="cell" className="w-12 shrink-0 text-right text-[13px] tabular" style={{ color: r.tone === "down" ? "var(--inhibitor)" : r.tone === "flat" ? "var(--faint)" : undefined }}>{r.value}</strong>
        </div>
      ))}
    </div>
  );
}
