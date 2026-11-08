"use client";
// Evidence rows come from the API (/evidence/{id}); validation from /eval/validation.
import { useEffect, useState } from "react";
import { api } from "../api";

export interface EvidenceRow {
  id: string;
  short: string;
  title: string;
  authors: string;
  year: number | string;
  journal: string;
  value_used: string;
  location: string;
  note: string;
  url?: string;
  verified: boolean;
}

// IDs used by the UI prototype -> real ids in the evidence table.
const ALIAS: Record<string, string> = {
  EVID_LINK_IRON_010: "EVID_LINK_IRON_005", ABS_MOD_IRON_010: "ABS_MOD_IRON_004",
  EVID_LINK_IRON_030: "EVID_LINK_IRON_009", ABS_MOD_IRON_020: "ABS_MOD_IRON_006",
  EVID_LINK_IRON_020: "EVID_LINK_IRON_010", ABS_MOD_IRON_030: "ABS_MOD_IRON_009",
  ABS_BASE_MONSEN: "ABS_BASE_IRON_006", ENGINE_FLOOR: "ASSUME_001",
};
export const realId = (id: string) => ALIAS[id] ?? id;

// Known short labels so chips render before the row loads.
const SHORT: Record<string, string> = {
  EVID_LINK_IRON_005: "Hurrell et al., 1999", ABS_MOD_IRON_004: "Hurrell et al., 1999", ABS_MOD_IRON_003: "Hurrell et al., 1999",
  ABS_MOD_IRON_002: "Hurrell et al., 1999", EVID_LINK_IRON_009: "Hallberg et al., 1989", ABS_MOD_IRON_006: "Hallberg et al., 1989",
  EVID_LINK_IRON_010: "Hallberg et al., 1991", ABS_MOD_IRON_009: "Hallberg et al., 1991", ABS_BASE_IRON_006: "Monsen & Balintfy, 1982",
  EVID_LINK_IRON_011: "Morck et al., 1983", ASSUME_001: "Engine assumption",
};

const cache = new Map<string, EvidenceRow>();

/* eslint-disable @typescript-eslint/no-explicit-any */
const shortOf = (p: any) => (p ? `${String(p.authors ?? "").split(/[ ,]/)[0]}${String(p.authors ?? "").includes(",") ? " et al." : ""}, ${p.year}` : "Source");

function toRow(id: string, d: any): EvidenceRow {
  if (d.kind === "paper") {
    const p = d.paper;
    return { id, short: shortOf(p), title: p.title, authors: p.authors, year: p.year, journal: p.journal, value_used: "", location: p.volume_pages ?? "",
      note: p.notes ?? "", url: p.doi_or_url || undefined, verified: String(p.citation_verified).toLowerCase() === "true" };
  }
  if (d.kind === "assumption") {
    const e = d.entity, p = d.papers?.[0];
    return { id, short: "Engine assumption", title: e.name?.replaceAll("_", " ") ?? id, authors: p?.authors ?? "Absorb team", year: p?.year ?? "",
      journal: "Engine assumption", value_used: e.description, location: "engine_assumptions.csv", note: e.rationale, url: p?.doi_or_url || undefined, verified: false };
  }
  const links: any[] = d.kind === "evidence_link" ? [{ ...d.link, paper: d.paper }] : d.evidence ?? [];
  const link = links.find((l) => l.evidence_role === "Primary_Support" && l.paper) ?? links.find((l) => l.paper) ?? links[0] ?? {};
  const p = link.paper;
  const val = link.quantitative_value_used || (link.quantitative_lower_used ? `${link.quantitative_lower_used} to ${link.quantitative_upper_used}` : "");
  const value = val ? `${val} ${link.quantitative_unit ?? ""}`.trim() : d.entity?.effect_interpretation ?? d.entity?.evidence_summary ?? "";
  return {
    id, short: p ? shortOf(p) : SHORT[id] ?? "Source", title: p?.title ?? id, authors: p?.authors ?? "", year: p?.year ?? "",
    journal: p?.journal ?? "", value_used: value, location: p?.volume_pages ?? "",
    note: link.synthesis_notes || d.entity?.applicability_notes || "", url: p?.doi_or_url || undefined,
    verified: String(link.human_verified ?? d.entity?.human_verified).toLowerCase() === "true",
  };
}

export async function fetchEvidence(id: string): Promise<EvidenceRow> {
  const rid = realId(id);
  const hit = cache.get(rid);
  if (hit) return hit;
  const row = toRow(rid, await api.get<any>(`/evidence/${encodeURIComponent(rid)}`));
  cache.set(rid, row);
  return row;
}

export const evidenceShort = (id: string) => cache.get(realId(id))?.short ?? SHORT[realId(id)] ?? "See source";

export function useEvidence(id: string | null) {
  const [row, setRow] = useState<EvidenceRow | null>(null);
  const [error, setError] = useState(false);
  useEffect(() => {
    setRow(null); setError(false);
    if (!id) return;
    let live = true;
    fetchEvidence(id).then((r) => live && setRow(r)).catch(() => live && setError(true));
    return () => { live = false; };
  }, [id]);
  return { row, error };
}

// ---------------------------------------------------------------- validation (/eval/validation)
export type ValidationView = {
  mae_pp: number | null;
  n: number;
  rows: { meal: string; study: string; measured: number; predicted: number }[];
  relative: { label: string; avail: number; published: string }[];
};

export async function loadValidation(): Promise<ValidationView> {
  const v = await api.get<any>("/eval/validation");
  const rows = (v.rows as any[]).filter((r) => r.split === "held_out")
    .map((r) => ({ meal: `${r.meal}: ${r.comparison}`, study: r.paper ?? r.paper_id, measured: Math.abs(r.measured_change_pct), predicted: Math.abs(r.predicted_change_pct) }));
  const relative = (v.rows as any[]).filter((r) => r.paper_id === "IRON_013")
    .map((r) => ({ label: String(r.comparison).replace(" vs water", "").replace(/^./, (c: string) => c.toUpperCase()),
      avail: Math.round(Math.abs(r.predicted_change_pct)),
      published: r.measured_range ? `Hurrell 1999 measured ${Math.abs(r.measured_range[1])} to ${Math.abs(r.measured_range[0])}%` : `Hurrell 1999 measured ${Math.abs(r.measured_change_pct)}%` }));
  return { mae_pp: v.summary?.held_out?.mae_pp ?? null, n: v.summary?.held_out?.n ?? rows.length, rows, relative };
}
