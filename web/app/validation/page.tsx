"use client";
import type { ValidationReport } from "@/lib/types";
import { useApi } from "@/lib/api";
import ValidationScatter from "@/components/charts/ValidationScatter";

export default function ValidationPage() {
  const { data, error } = useApi<ValidationReport>("/eval/validation");
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold">How accurate is Absorb?</h1>
        <p className="text-sm text-ink-2">We ran the engine on meals from published human absorption studies and compared its predictions with what the studies measured.</p>
      </div>
      {error && <p className="text-critical text-sm">{error.message}</p>}
      {data && (
        <>
          <div className="grid grid-cols-2 gap-3">
            <div className="card p-3"><div className="text-xs text-ink-2">Study meals</div><div className="text-2xl font-bold tabular">{data.n}</div></div>
            <div className="card p-3"><div className="text-xs text-ink-2">Mean absolute error</div><div className="text-2xl font-bold tabular">{data.mae_pp} <span className="text-sm font-medium text-ink-2">pp</span></div></div>
          </div>
          <div className="card p-3"><ValidationScatter report={data} /></div>
          <section className="card p-4">
            <h2 className="font-semibold mb-2">Relative effects</h2>
            <table className="w-full text-sm tabular">
              <thead className="text-xs text-ink-2 text-left"><tr><th className="pb-1">Change</th><th>Engine</th><th>Published</th></tr></thead>
              <tbody>
                {data.relative_effects.map((r) => (
                  <tr key={r.label} className="border-t border-border"><td className="py-1.5">{r.label}</td><td>{r.predicted}</td><td className="text-ink-2">{r.measured}</td></tr>
                ))}
              </tbody>
            </table>
          </section>
          <p className="text-xs text-muted">Compared against published group means, not individuals. Individual absorption varies, especially with iron stores.</p>
        </>
      )}
    </div>
  );
}
