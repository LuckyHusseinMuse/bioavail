"use client";
// Interaction map: the G-Research centrepiece. Nodes = iron forms, enhancers and inhibitors.
// Edges: green "raises" / red "blocks"; thickness = effect size; edges active in this meal
// glow and animate, the rest fade. Colour is never the only cue: every edge has a text label.
import "@xyflow/react/dist/style.css";
import { Background, Handle, Position, ReactFlow, type Edge, type Node, type NodeProps } from "@xyflow/react";
import { useMemo, useState } from "react";
import type { EngineResult, InteractionGraph } from "@/lib/types";
import { FACTOR_LABEL } from "@/lib/format";
import { factorStates } from "./activeFactors";
import EvidenceSheet from "../EvidenceSheet";

// Fixed positions (phone-first, vertical): enhancers top, iron middle, inhibitors bottom.
const POS: Record<string, { x: number; y: number }> = {
  vitamin_c: { x: -60, y: 0 },
  mfp: { x: 130, y: 0 },
  nonhaem: { x: 60, y: 150 },
  haem: { x: 250, y: 150 },
  phytate: { x: -130, y: 300 },
  polyphenols: { x: 60, y: 300 },
  calcium: { x: 250, y: 300 },
};

type NodeData = { label: string; kind: "iron" | "enhancer" | "inhibitor"; active: boolean; detail?: string; hasResult: boolean };

function FactorNode({ data }: NodeProps<Node<NodeData>>) {
  const ring = data.kind === "iron" ? "var(--series-1)" : data.kind === "enhancer" ? "var(--good)" : "var(--critical)";
  const dim = data.hasResult && !data.active;
  return (
    <div
      className="rounded-2xl px-3 py-2 text-center w-[150px] transition-all"
      style={{
        background: "var(--surface)",
        border: `2px solid ${ring}`,
        opacity: dim ? 0.35 : 1,
        boxShadow: data.active && data.hasResult ? `0 0 0 4px color-mix(in oklab, ${ring} 22%, transparent)` : "none",
      }}
    >
      {/* Four handles so every edge leaves from the side facing its target (no loops). */}
      <Handle id="t-top" type="target" position={Position.Top} style={{ opacity: 0 }} />
      <Handle id="t-bottom" type="target" position={Position.Bottom} style={{ opacity: 0 }} />
      <Handle id="s-top" type="source" position={Position.Top} style={{ opacity: 0 }} />
      <div className="text-[13px] font-semibold leading-tight text-ink">{data.label}</div>
      <div className="text-[11px] text-ink-2 mt-0.5 tabular">
        {data.detail ?? (data.kind === "enhancer" ? "enhancer" : data.kind === "inhibitor" ? "inhibitor" : "iron")}
      </div>
      <Handle id="s-bottom" type="source" position={Position.Bottom} style={{ opacity: 0 }} />
    </div>
  );
}
const nodeTypes = { factor: FactorNode };

export default function InteractionMap({ graph, result, height = 440 }: { graph: InteractionGraph; result?: EngineResult | null; height?: number }) {
  const [evidenceId, setEvidenceId] = useState<string | null>(null);
  const states = useMemo(() => factorStates(result), [result]);
  const hasResult = !!result;

  const nodes: Node<NodeData>[] = useMemo(
    () =>
      graph.nodes.map((n) => {
        const s = states[n.id];
        let detail: string | undefined;
        if (s?.amount != null && s.active) detail = `${s.amount} ${s.unit ?? ""}${s.multiplier != null && s.multiplier !== 1 ? ` · ×${s.multiplier}` : ""}`;
        return {
          id: n.id, type: "factor", position: POS[n.id] ?? { x: 0, y: 0 }, draggable: false,
          data: { label: n.label, kind: n.kind, active: !!s?.active, detail, hasResult },
        };
      }),
    [graph, states, hasResult],
  );

  const edges: Edge[] = useMemo(
    () =>
      graph.edges.map((e) => {
        const active = !hasResult || (!!states[e.source]?.active && !!states[e.target]?.active);
        const color = e.effect === "enhance" ? "var(--good)" : "var(--critical)";
        const mult = states[e.source]?.multiplier;
        const showMult = hasResult && active && e.effect === "inhibit" && mult != null && mult < 1;
        const up = (POS[e.source]?.y ?? 0) > (POS[e.target]?.y ?? 0);
        return {
          id: e.id, source: e.source, target: e.target,
          sourceHandle: up ? "s-top" : "s-bottom",
          targetHandle: up ? "t-bottom" : "t-top",
          animated: hasResult && active,
          label: showMult ? `${e.label} ×${mult}` : e.label,
          labelStyle: { fill: "var(--text)", fontSize: 11, fontWeight: 600 },
          labelBgStyle: { fill: "var(--surface)" },
          labelBgPadding: [4, 2] as [number, number],
          labelBgBorderRadius: 6,
          data: { modifier_id: e.modifier_id },
          style: {
            stroke: color,
            strokeWidth: 1.5 + e.strength * 4,
            opacity: active ? 1 : 0.15,
            filter: hasResult && active ? `drop-shadow(0 0 4px ${color})` : undefined,
          },
        };
      }),
    [graph, states, hasResult],
  );

  return (
    <div>
      <div className="card overflow-hidden" style={{ height }}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          fitView
          fitViewOptions={{ padding: 0.12 }}
          nodesConnectable={false}
          elementsSelectable
          panOnDrag={false}
          zoomOnScroll={false}
          zoomOnPinch
          preventScrolling={false}
          onEdgeClick={(_, edge) => setEvidenceId((edge.data as { modifier_id?: string })?.modifier_id ?? null)}
          proOptions={{ hideAttribution: true }}
        >
          <Background color="var(--grid)" gap={24} />
        </ReactFlow>
      </div>
      <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2 text-xs text-ink-2">
        <span className="flex items-center gap-1.5"><span className="inline-block w-5 h-[3px] rounded" style={{ background: "var(--good)" }} />raises absorption</span>
        <span className="flex items-center gap-1.5"><span className="inline-block w-5 h-[3px] rounded" style={{ background: "var(--critical)" }} />blocks absorption</span>
        <span>Thicker = stronger effect · tap an edge for the evidence</span>
        {hasResult && <span>Glowing = active in this meal</span>}
      </div>
      {result && (
        <ul className="sr-only">
          {Object.entries(states).filter(([, s]) => s.active).map(([k, s]) => (
            <li key={k}>{FACTOR_LABEL[k] ?? k}: {s.amount} {s.unit} {s.multiplier != null ? `multiplier ${s.multiplier}` : ""}</li>
          ))}
        </ul>
      )}
      <EvidenceSheet id={evidenceId} onClose={() => setEvidenceId(null)} />
    </div>
  );
}
