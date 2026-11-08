"use client";
import { useEffect, useState } from "react";
import type { Food } from "@/lib/types";
import { api } from "@/lib/api";
import { IconSearch } from "./Icons";

export default function FoodSearch({ onPick, placeholder = "Search foods and drinks", autoFocus }: { onPick: (f: Food) => void; placeholder?: string; autoFocus?: boolean }) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<Food[]>([]);
  useEffect(() => {
    const t = setTimeout(() => api.get<Food[]>(`/foods?q=${encodeURIComponent(q)}`).then(setResults).catch(() => setResults([])), 200);
    return () => clearTimeout(t);
  }, [q]);
  return (
    <div>
      <label className="relative block">
        <span className="absolute left-3 top-1/2 -translate-y-1/2 text-muted"><IconSearch className="w-5 h-5" /></span>
        <input className="input !pl-10" value={q} onChange={(e) => setQ(e.target.value)} placeholder={placeholder} autoFocus={autoFocus} />
      </label>
      <ul className="mt-2 divide-y divide-border max-h-72 overflow-y-auto">
        {results.map((f) => (
          <li key={f.food_code}>
            <button className="w-full text-left py-2.5 flex justify-between gap-2" onClick={() => onPick(f)}>
              <span>{f.name}</span>
              <span className="text-xs text-muted shrink-0 tabular">{f.serving_g} g · {f.group}</span>
            </button>
          </li>
        ))}
        {!results.length && <li className="py-3 text-sm text-muted">No matches</li>}
      </ul>
    </div>
  );
}
