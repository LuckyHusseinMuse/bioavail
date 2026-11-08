"use client";
// Evidence panel: every number traceable to a paper. Opens as a bottom sheet.
import { useEffect, useState } from "react";
import type { Evidence } from "@/lib/types";
import { api } from "@/lib/api";
import { IconX } from "./Icons";

export default function EvidenceSheet({ id, onClose }: { id: string | null; onClose: () => void }) {
  const [ev, setEv] = useState<Evidence | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    setEv(null); setErr(null);
    api.get<Evidence>(`/evidence/${encodeURIComponent(id)}`).then(setEv).catch((e) => setErr(e.message));
  }, [id]);

  if (!id) return null;
  return (
    <div className="fixed inset-0 z-[60] flex items-end justify-center bg-black/40" onClick={onClose} role="dialog" aria-modal aria-label="Evidence">
      <div className="card w-full max-w-xl rounded-b-none p-5 pb-[calc(1.25rem+env(safe-area-inset-bottom))] max-h-[70dvh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
        <div className="flex justify-between items-start gap-3">
          <div>
            <div className="text-xs text-muted font-mono">{id}</div>
            <h3 className="font-semibold text-lg">{ev?.short ?? (err ? "Evidence unavailable" : "Loading…")}</h3>
          </div>
          <button onClick={onClose} className="p-2 -m-2 text-muted" aria-label="Close"><IconX /></button>
        </div>
        {err && <p className="text-sm text-critical mt-2">{err}</p>}
        {ev && (
          <div className="mt-3 space-y-3 text-sm">
            <div className="rounded-xl bg-surface-2 p-3"><div className="text-xs text-muted mb-1">Finding</div>{ev.quantitative_value}</div>
            <p className="text-ink-2">{ev.citation}</p>
            {ev.notes && <p className="text-ink-2">{ev.notes}</p>}
            <div className="flex items-center justify-between">
              <span className={`text-xs font-medium ${ev.human_verified ? "text-good-ink" : "text-muted"}`}>
                {ev.human_verified ? "✓ Checked against the paper by a second person" : "Not yet independently checked"}
              </span>
              {ev.url && <a href={ev.url} target="_blank" rel="noreferrer" className="text-brand font-medium">Open paper ↗</a>}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
