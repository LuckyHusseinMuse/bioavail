"use client";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import type { ChatEvent, ChatMessage, Citation } from "@/lib/types";
import { api, streamChat, useApi } from "@/lib/api";
import CitedText from "@/components/CitedText";
import { notifyAlertsChanged } from "@/components/AppShell";
import { IconClock } from "@/components/Icons";

const TOOL_LABEL: Record<string, string> = {
  search_foods: "Searched foods", get_food: "Looked up a food", score_meal: "Scored a meal", simulate_change: "Simulated a change",
  get_rules: "Checked the rules", get_evidence: "Read the evidence", get_daily_summary: "Checked today", get_meal_history: "Read your meals",
  get_patterns: "Checked your week", create_alert: "Prepared a reminder",
};
const SUGGESTIONS = ["Is tea really that bad for iron?", "Why was lunch so low?", "What can I add to porridge?"];

type Live = ChatMessage & { pending?: boolean; handoff?: string; offer?: { type: string; when: string; message: string }; grounded?: boolean };

function ChatInner() {
  const params = useSearchParams();
  const { data: history } = useApi<ChatMessage[]>("/chat/history");
  const [msgs, setMsgs] = useState<Live[]>([]);
  const [input, setInput] = useState(params.get("q") ?? "");
  const [busy, setBusy] = useState(false);
  const [toolNow, setToolNow] = useState<string | null>(null);
  const bottom = useRef<HTMLDivElement>(null);

  useEffect(() => { if (history && !msgs.length) setMsgs(history); }, [history]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { bottom.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs, toolNow]);

  async function send(text: string) {
    if (!text.trim() || busy) return;
    setInput("");
    setBusy(true);
    const now = new Date().toISOString();
    const aid = `live-${Date.now()}`;
    setMsgs((m) => [...m, { id: `u-${Date.now()}`, role: "user", content: text, sent_at: now }, { id: aid, role: "assistant", content: "", sent_at: now, pending: true, tools: [] }]);
    const patch = (fn: (m: Live) => Live) => setMsgs((ms) => ms.map((m) => (m.id === aid ? fn(m) : m)));

    await streamChat(text, (e: ChatEvent) => {
      switch (e.type) {
        case "tool": setToolNow(e.name); patch((m) => ({ ...m, tools: [...(m.tools ?? []), e.name] })); break;
        case "delta": setToolNow(null); patch((m) => ({ ...m, content: m.content + e.text })); break;
        case "citations": patch((m) => ({ ...m, citations: e.citations as Citation[] })); break;
        case "handoff": patch((m) => ({ ...m, handoff: e.meal_id })); break;
        case "offer_alert": patch((m) => ({ ...m, offer: e.alert })); break;
        case "done": patch((m) => ({ ...m, pending: false, grounded: e.grounded })); break;
        case "error": patch((m) => ({ ...m, pending: false, content: m.content || `Sorry, something went wrong: ${e.message}` })); break;
      }
    }).catch((err) => patch((m) => ({ ...m, pending: false, content: `Connection lost: ${err.message}` })));
    setToolNow(null);
    setBusy(false);
  }

  async function acceptAlert(id: string, offer: NonNullable<Live["offer"]>) {
    const mins = Number(/\+(\d+)m/.exec(offer.when)?.[1] ?? 60);
    await api.post("/alerts", { type: offer.type, message: offer.message, scheduled_for: new Date(Date.now() + mins * 60000).toISOString() });
    setMsgs((ms) => ms.map((m) => (m.id === id ? { ...m, offer: undefined, content: m.content + `\n\n**Reminder set** for ${mins} minutes from now.` } : m)));
    notifyAlertsChanged();
  }

  return (
    <div className="flex flex-col min-h-[calc(100dvh-10rem)]">
      <div className="flex-1 space-y-3">
        {msgs.length === 0 && (
          <div className="text-center text-ink-2 py-8">
            <h1 className="text-xl font-bold text-ink">Ask about your iron</h1>
            <p className="text-sm mt-1">Answers come from the absorption engine and published studies, not guesses.</p>
          </div>
        )}
        {msgs.map((m) => (
          <div key={m.id} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-[88%] rounded-2xl px-3.5 py-2.5 text-sm ${m.role === "user" ? "bg-brand text-white rounded-br-md" : "card rounded-bl-md"}`}>
              {m.role === "assistant" && !!m.tools?.length && (
                <div className="flex flex-wrap gap-1 mb-1.5">
                  {[...new Set(m.tools)].map((t) => <span key={t} className="text-[10px] px-1.5 py-0.5 rounded bg-surface-2 text-ink-2">✓ {TOOL_LABEL[t] ?? t}</span>)}
                </div>
              )}
              {m.role === "assistant" ? (
                m.content ? <CitedText text={m.content} citations={m.citations} /> : <span className="text-muted animate-pulse">{toolNow ? `${TOOL_LABEL[toolNow] ?? toolNow}…` : "Thinking…"}</span>
              ) : m.content}
              {m.handoff && <Link href={`/meal/${m.handoff}`} className="btn btn-ghost !min-h-9 mt-2 w-full text-sm">Find a fix for this meal</Link>}
              {m.offer && (
                <button onClick={() => acceptAlert(m.id, m.offer!)} className="btn btn-ghost !min-h-9 mt-2 w-full text-sm"><IconClock className="w-4 h-4" />Remind me: “{m.offer.message}”</button>
              )}
              {m.grounded === false && <p className="text-[11px] text-critical mt-1">Some numbers in this reply could not be verified against the engine.</p>}
            </div>
          </div>
        ))}
        <div ref={bottom} />
      </div>

      <div className="sticky bottom-20 bg-bg pt-2">
        {msgs.length < 2 && (
          <div className="flex gap-2 overflow-x-auto pb-2 -mx-4 px-4">
            {SUGGESTIONS.map((s) => <button key={s} onClick={() => send(s)} className="shrink-0 text-sm px-3 py-1.5 rounded-full border border-border bg-surface">{s}</button>)}
          </div>
        )}
        <form onSubmit={(e) => { e.preventDefault(); send(input); }} className="flex gap-2">
          <input className="input" value={input} onChange={(e) => setInput(e.target.value)} placeholder="Ask about a meal…" aria-label="Message" />
          <button className="btn btn-primary" disabled={busy || !input.trim()}>Send</button>
        </form>
        <p className="text-[10px] text-muted text-center mt-1">Not medical advice. For symptoms or supplements, see a GP or pharmacist.</p>
      </div>
    </div>
  );
}

export default function ChatPage() {
  return <Suspense><ChatInner /></Suspense>;
}
