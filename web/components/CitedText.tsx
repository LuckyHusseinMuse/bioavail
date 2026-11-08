"use client";
// Renders agent text: **bold**, paragraphs, and [EVID_ID] markers as tappable citation chips.
import { Fragment, useState } from "react";
import type { Citation } from "@/lib/types";
import EvidenceSheet from "./EvidenceSheet";

export default function CitedText({ text, citations = [] }: { text: string; citations?: Citation[] }) {
  const [open, setOpen] = useState<string | null>(null);
  const shortFor = (id: string) => citations.find((c) => c.evidence_id === id)?.short ?? "source";

  const renderInline = (s: string, key: string) =>
    s.split(/(\[[A-Z][A-Z0-9_]+\]|\*\*[^*]+\*\*)/g).map((part, i) => {
      if (/^\[[A-Z][A-Z0-9_]+\]$/.test(part)) {
        const id = part.slice(1, -1);
        return (
          <button key={`${key}-${i}`} onClick={() => setOpen(id)} className="inline-flex items-center mx-0.5 px-1.5 rounded-md bg-surface-2 border border-border text-[11px] font-medium text-brand align-baseline">
            {shortFor(id)}
          </button>
        );
      }
      if (part.startsWith("**")) return <strong key={`${key}-${i}`}>{part.slice(2, -2)}</strong>;
      return <Fragment key={`${key}-${i}`}>{part}</Fragment>;
    });

  return (
    <>
      <div className="space-y-2 leading-relaxed">
        {text.split(/\n{2,}/).map((p, i) => <p key={i}>{renderInline(p, String(i))}</p>)}
      </div>
      <EvidenceSheet id={open} onClose={() => setOpen(null)} />
    </>
  );
}
