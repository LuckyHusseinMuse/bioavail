"use client";
// SCREEN 7: Absorb, Map view. React Flow network. Green edges enhance, red inhibit (always labelled),
// thickness = effect size in THIS meal, active edges glow and flow, inactive ones fade.
// Tapping a node shows a tooltip card with one line and an Evidence link.
import "@xyflow/react/dist/style.css";
import { Handle, Position, ReactFlow, type Edge, type Node, type NodeProps } from "@xyflow/react";
import { ArrowUpRight, Minus, Plus } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useMemo, useState } from "react";
import type { EngineResult } from "@/lib/engine/types";
import { cn } from "../ui/primitives";

type Kind = "iron" | "good" | "bad";
type Def = { id: string; label: string; kind: Kind; x: number; y: number; r: number; evidence: string };
const DEFS: Def[] = [
  { id: "iron", label: "Iron", kind: "iron", x: 150, y: 170, r: 46, evidence: "ABS_BASE_MONSEN" },
  { id: "vitamin_c", label: "Vitamin C", kind: "good", x: 30, y: 30, r: 36, evidence: "ABS_BASE_MONSEN" },
  { id: "mfp", label: "Meat, fish, poultry", kind: "good", x: 270, y: 30, r: 38, evidence: "ABS_BASE_MONSEN" },
  { id: "polyphenols", label: "Polyphenols", kind: "bad", x: 20, y: 300, r: 38, evidence: "EVID_LINK_IRON_010" },
  { id: "phytate", label: "Phytate", kind: "bad", x: 155, y: 360, r: 34, evidence: "EVID_LINK_IRON_030" },
  { id: "calcium", label: "Calcium", kind: "bad", x: 285, y: 300, r: 34, evidence: "EVID_LINK_IRON_020" },
];

const HANDLE = { left: "50%", top: "50%", opacity: 0, width: 1, height: 1, minWidth: 0, minHeight: 0, border: 0 };

type NData = { def: Def; active: boolean; selected: boolean; dim: boolean };
function Circle({ data }: NodeProps<Node<NData>>) {
  const { def, active, selected, dim } = data;
  const bg = def.kind === "iron" ? "var(--iron)" : def.kind === "good" ? "color-mix(in oklab, var(--enhancer) 20%, var(--surface))" : "color-mix(in oklab, var(--inhibitor) 16%, var(--surface))";
  const ink = def.kind === "iron" ? "var(--iron-ink)" : def.kind === "good" ? "var(--enhancer)" : "var(--inhibitor)";
  const ring = def.kind === "good" ? "var(--enhancer)" : def.kind === "bad" ? "var(--inhibitor)" : "var(--iron)";
  return (
    <div className="grid place-items-center rounded-full text-center font-bold leading-tight transition-all duration-300"
      style={{ width: def.r * 2, height: def.r * 2, background: bg, color: ink, opacity: dim ? 0.4 : 1, fontSize: def.kind === "iron" ? 16 : 11,
        border: `3px solid ${selected ? ring : "var(--surface)"}`, boxShadow: active && def.kind !== "iron" ? `0 0 0 6px color-mix(in oklab, ${ring} 16%, transparent)` : "var(--shadow)" }}>
      <Handle type="target" position={Position.Top} style={HANDLE} />
      <Handle type="source" position={Position.Top} style={HANDLE} />
      <span className="px-1.5">{def.label}</span>
    </div>
  );
}
const nodeTypes = { circle: Circle };

export function factorEffects(r: EngineResult) {
  const get = (f: string) => r.contributions.find((c) => c.factor === f);
  return {
    vitamin_c: { active: (get("vitamin_c")?.amount ?? 0) >= 10, size: Math.min(1, (get("vitamin_c")?.amount ?? 0) / 100), line: get("vitamin_c") ? `${get("vitamin_c")!.amount} mg in this meal. Vitamin C helps your body take up non-haem iron.` : "None in this meal. Vitamin C helps your body take up non-haem iron." },
    mfp: { active: !!get("mfp"), size: Math.min(1, (get("mfp")?.amount ?? 0) / 120), line: get("mfp") ? `${get("mfp")!.amount} g in this meal. Meat, fish and poultry add haem iron and boost non-haem absorption.` : "None in this meal. Meat, fish and poultry boost non-haem iron absorption." },
    polyphenols: { active: (get("polyphenols")?.multiplier ?? 1) < 0.9, size: 1 - (get("polyphenols")?.multiplier ?? 1), line: get("polyphenols") ? `${get("polyphenols")!.amount} mg, multiplying non-haem absorption by ${get("polyphenols")!.multiplier}. Tea polyphenols bind iron.` : "None in this meal. Tea and coffee polyphenols bind iron." },
    phytate: { active: (get("phytate")?.multiplier ?? 1) < 0.9, size: 1 - (get("phytate")?.multiplier ?? 1), line: get("phytate") ? `${get("phytate")!.amount} mg, multiplying absorption by ${get("phytate")!.multiplier}. Phytate makes plant iron less available.` : "None measured. Phytate in grains and legumes makes plant iron less available." },
    calcium: { active: (get("calcium")?.multiplier ?? 1) < 0.95, size: 1 - (get("calcium")?.multiplier ?? 1), line: get("calcium") ? `${get("calcium")!.amount} mg, multiplying absorption by ${get("calcium")!.multiplier}.` : "Little calcium in this meal, so little effect." },
    iron: { active: true, size: 1, line: `This meal contains ${r.iron_mg} mg of iron, ${r.haem_mg} mg of it haem.` },
  } as Record<string, { active: boolean; size: number; line: string }>;
}

export default function InteractionMap({ result, onEvidence }: { result: EngineResult; onEvidence: (id: string) => void }) {
  const fx = useMemo(() => factorEffects(result), [result]);
  const strongest = useMemo(() => Object.entries(fx).filter(([k]) => k !== "iron").sort((a, b) => b[1].size - a[1].size)[0]?.[0], [fx]);
  const [sel, setSel] = useState<string>(strongest ?? "iron");
  const def = DEFS.find((d) => d.id === sel)!;

  const nodes: Node<NData>[] = DEFS.map((d) => ({
    id: d.id, type: "circle", position: { x: d.x - d.r, y: d.y - d.r }, draggable: false,
    data: { def: d, active: fx[d.id].active, selected: sel === d.id, dim: d.id !== "iron" && !fx[d.id].active },
  }));
  const edges: Edge[] = DEFS.filter((d) => d.id !== "iron").map((d) => {
    const e = fx[d.id];
    const color = d.kind === "good" ? "var(--enhancer)" : "var(--inhibitor)";
    return {
      id: `e-${d.id}`, source: d.id, target: "iron", type: "straight", animated: e.active,
      style: { stroke: color, strokeWidth: 1.5 + e.size * 9, opacity: e.active ? 1 : 0.18, filter: e.active ? `drop-shadow(0 0 6px ${color})` : undefined, strokeLinecap: "round" },
    };
  });

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted">
        <span className="flex items-center gap-1.5"><Plus className="h-3.5 w-3.5 text-enhancer" /><i className="h-[3px] w-5 rounded bg-enhancer" />Enhances</span>
        <span className="flex items-center gap-1.5"><Minus className="h-3.5 w-3.5 text-inhibitor" /><i className="h-[3px] w-5 rounded bg-inhibitor" />Inhibits</span>
        <span>Line weight shows effect size</span>
      </div>
      <div className="h-[400px] overflow-hidden rounded-2xl border border-border bg-surface">
        <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} fitView fitViewOptions={{ padding: 0.08 }}
          nodesConnectable={false} panOnDrag={false} zoomOnScroll={false} zoomOnPinch={false} zoomOnDoubleClick={false} preventScrolling={false}
          onNodeClick={(_, n) => setSel(n.id)} proOptions={{ hideAttribution: true }} />
      </div>
      <AnimatePresence mode="wait">
        <motion.div key={sel} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
          className="flex gap-3 rounded-2xl border border-border bg-surface p-4 shadow-card">
          <span className={cn("mt-1 h-2.5 w-2.5 shrink-0 rounded-full", def.kind === "bad" ? "bg-inhibitor" : def.kind === "good" ? "bg-enhancer" : "bg-iron")} />
          <div className="flex-1">
            <p className="font-bold">{def.label} <span className="text-xs font-semibold text-muted">{def.kind === "bad" ? "· inhibits" : def.kind === "good" ? "· enhances" : ""}</span></p>
            <p className="mt-0.5 text-sm text-muted">{fx[sel].line}</p>
            <button onClick={() => onEvidence(def.evidence)} className="mt-1.5 inline-flex min-h-9 items-center gap-1 text-sm font-bold text-primary">Evidence <ArrowUpRight className="h-4 w-4" /></button>
          </div>
        </motion.div>
      </AnimatePresence>
    </div>
  );
}
