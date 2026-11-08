"use client";
// SCREEN 9: Evidence sheet (bottom sheet over Absorb). Rows come from the evidence table via /evidence/{id}.
import { BadgeCheck, ExternalLink, FileText, Loader2 } from "lucide-react";
import { Sheet } from "./shell";
import { Button } from "./ui/primitives";
import { useEvidence } from "@/lib/engine/evidence";

export default function EvidenceSheet({ id, onClose }: { id: string | null; onClose: () => void }) {
  const { row: ev, error } = useEvidence(id);
  return (
    <Sheet open={!!id} onOpenChange={(o) => !o && onClose()} title="Evidence">
      {ev ? (
        <div className="space-y-4">
          <div className="flex items-start gap-3">
            <span className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-primary/10 text-primary"><FileText className="h-5 w-5" /></span>
            <div>
              <p className="text-[11px] font-bold uppercase tracking-[0.08em] text-faint">{ev.journal}</p>
              <h3 className="mt-0.5 text-[17px] font-bold leading-snug">{ev.title}</h3>
            </div>
          </div>
          <dl className="divide-y divide-border rounded-2xl border border-border text-sm">
            {[
              ["Authors", ev.authors],
              ["Year", String(ev.year)],
              ["Value used", ev.value_used],
              ["Volume / pages", ev.location],
            ].filter(([, v]) => v).map(([k, v]) => (
              <div key={k} className="flex gap-3 px-4 py-3">
                <dt className="w-28 shrink-0 text-muted">{k}</dt>
                <dd className="font-semibold">{v}</dd>
              </div>
            ))}
          </dl>
          {ev.note && <p className="rounded-xl bg-surface-2 p-3 text-sm text-muted">{ev.note}</p>}
          <p className={`flex items-center gap-1.5 text-xs font-semibold ${ev.verified ? "text-enhancer" : "text-faint"}`}>
            <BadgeCheck className="h-4 w-4" />{ev.verified ? "Checked against the paper by a second person" : "Not yet independently checked"}
          </p>
          <div className="grid grid-cols-2 gap-2">
            {ev.url ? <Button variant="outline" href={ev.url}><ExternalLink className="h-4 w-4" />Open paper</Button> : <span />}
            <Button onClick={onClose} className={ev.url ? "" : "col-span-2"}>Close</Button>
          </div>
        </div>
      ) : error ? (
        <p className="py-6 text-sm text-muted">No evidence row for {id}.</p>
      ) : (
        <p className="flex items-center gap-2 py-6 text-sm text-muted"><Loader2 className="h-4 w-4 animate-spin" />Loading the source…</p>
      )}
    </Sheet>
  );
}
