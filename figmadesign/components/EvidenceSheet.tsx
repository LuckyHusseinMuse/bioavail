"use client";
// SCREEN 9: Evidence sheet (bottom sheet over Absorb)
import { BadgeCheck, ExternalLink, FileText } from "lucide-react";
import { Sheet } from "./shell";
import { Button } from "./ui/primitives";
import { EVIDENCE } from "@/lib/engine/evidence";

export default function EvidenceSheet({ id, onClose }: { id: string | null; onClose: () => void }) {
  const ev = id ? EVIDENCE[id] : null;
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
              ["Table or page", ev.location],
            ].map(([k, v]) => (
              <div key={k} className="flex gap-3 px-4 py-3">
                <dt className="w-28 shrink-0 text-muted">{k}</dt>
                <dd className="font-semibold">{v}</dd>
              </div>
            ))}
          </dl>
          <p className="rounded-xl bg-surface-2 p-3 text-sm text-muted">{ev.note}</p>
          <p className={`flex items-center gap-1.5 text-xs font-semibold ${ev.verified ? "text-enhancer" : "text-faint"}`}>
            <BadgeCheck className="h-4 w-4" />{ev.verified ? "Checked against the paper by a second person" : "Not yet independently checked"}
          </p>
          <div className="grid grid-cols-2 gap-2">
            {ev.url ? <Button variant="outline" href={ev.url}><ExternalLink className="h-4 w-4" />Open paper</Button> : <span />}
            <Button onClick={onClose} className={ev.url ? "" : "col-span-2"}>Close</Button>
          </div>
        </div>
      ) : (
        <p className="py-6 text-sm text-muted">No evidence row for {id}.</p>
      )}
    </Sheet>
  );
}
