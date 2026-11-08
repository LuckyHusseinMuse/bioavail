"use client";
// SCREEN 12: Chat (full screen, opened from the bubble) + refusal state
import { ArrowUpRight, ChevronLeft, SendHorizontal, ShieldAlert } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import EvidenceSheet from "@/components/EvidenceSheet";
import { Chip, cn } from "@/components/ui/primitives";
import { EVIDENCE } from "@/lib/engine/evidence";
import { chatReply, type ChatMsg } from "@/lib/logic";
import { timeOf, useStore } from "@/lib/store";

const STARTERS = ["Why was this low?", "What can I add?", "Remind me about tea"];

function Bubble({ m, onCite }: { m: ChatMsg; onCite: (id: string) => void }) {
  if (m.role === "user") return <div className="ml-auto max-w-[80%] rounded-[20px] rounded-br-md bg-primary px-4 py-2.5 text-[15px] text-primary-ink">{m.text}</div>;
  const [a, b] = m.text.split("{h}");
  return (
    <div className="flex items-end gap-2">
      <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-iron text-xs font-extrabold text-iron-ink">a</span>
      <div className={cn("max-w-[82%] rounded-[20px] rounded-bl-md border border-border bg-surface px-4 py-3 text-[15px] leading-relaxed shadow-card", m.refusal && "border-amber/40")}>
        {m.refusal && <p className="mb-1 flex items-center gap-1.5 text-xs font-bold text-amber"><ShieldAlert className="h-3.5 w-3.5" />Outside what Avail can advise on</p>}
        <p>{a}{m.highlight && <mark className="rounded-md bg-amber/25 px-1 font-bold text-ink">{m.highlight}</mark>}{b}</p>
        {m.cite && (
          <button onClick={() => onCite(m.cite!)} className="mt-2"><Chip tone="green" className="min-h-8">{EVIDENCE[m.cite]?.short ?? m.cite} <ArrowUpRight className="h-3.5 w-3.5" /></Chip></button>
        )}
      </div>
    </div>
  );
}

function ChatInner() {
  const router = useRouter();
  const params = useSearchParams();
  const chat = useStore((s) => s.chat);
  const addChat = useStore((s) => s.addChat);
  const addReminder = useStore((s) => s.addReminder);
  const meals = useStore((s) => s.meals);
  const currentId = useStore((s) => s.currentMealId);
  const meal = meals.find((m) => m.id === currentId) ?? meals.at(-1) ?? null;
  const [input, setInput] = useState("");
  const [typing, setTyping] = useState(false);
  const [cite, setCite] = useState<string | null>(null);
  const end = useRef<HTMLDivElement>(null);
  const seeded = useRef(false);

  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [chat, typing]);

  function send(text: string) {
    if (!text.trim() || typing) return;
    addChat({ role: "user", text });
    setInput("");
    setTyping(true);
    setTimeout(() => {
      const reply = chatReply(text, meal);
      addChat(reply);
      if (/remind/i.test(text) && /tea/i.test(text) && meal) {
        const at = timeOf(new Date(Date.parse(meal.eaten_at) + 120 * 60000).toISOString());
        addReminder({ kind: "drink", title: "Have your tea", time: at, repeat: "once", days: [], notify: true });
        toast.success(`Reminder set for ${at}`);
      }
      setTyping(false);
    }, 900);
  }

  // Prototype map deep links: ?demo=1 shows the design conversation, ?demo=refusal the refusal state.
  useEffect(() => {
    const d = params.get("demo");
    if (!d || seeded.current) return;
    seeded.current = true;
    const q = d === "refusal" ? "How much iron should I take?" : "Is tea really that bad for iron?";
    addChat({ role: "user", text: q });
    addChat(chatReply(q, meal));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="flex min-h-dvh flex-col sm:min-h-[844px]">
      <div className="sticky top-0 z-20 flex items-center gap-3 border-b border-border bg-bg/90 px-3 pb-3 pt-[max(12px,env(safe-area-inset-top))] backdrop-blur-md sm:pt-12">
        <button onClick={() => router.back()} aria-label="Back" className="grid h-11 w-11 place-items-center rounded-full hover:bg-surface-2"><ChevronLeft className="h-6 w-6" /></button>
        <span className="grid h-10 w-10 place-items-center rounded-full bg-iron text-base font-extrabold text-iron-ink">a</span>
        <div><h1 className="font-bold leading-tight">Avail guide</h1><p className="text-xs text-muted">Answers from the engine and published studies</p></div>
      </div>

      <div className="flex-1 space-y-4 px-4 py-4">
        {meal && <div className="flex justify-center"><Chip tone="grey">Asking about: {meal.label}, {timeOf(meal.eaten_at)}</Chip></div>}
        <AnimatePresence initial={false}>
          {chat.map((m) => (
            <motion.div key={m.id} initial={{ opacity: 0, y: 10, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }} transition={{ duration: 0.22 }}>
              <Bubble m={m} onCite={setCite} />
            </motion.div>
          ))}
        </AnimatePresence>
        {typing && (
          <div className="flex items-end gap-2">
            <span className="grid h-7 w-7 place-items-center rounded-full bg-iron text-xs font-extrabold text-iron-ink">a</span>
            <div className="flex gap-1 rounded-[20px] rounded-bl-md border border-border bg-surface px-4 py-3.5">
              {[0, 1, 2].map((i) => <motion.i key={i} className="h-2 w-2 rounded-full bg-faint" animate={{ y: [0, -4, 0] }} transition={{ duration: 0.6, repeat: Infinity, delay: i * 0.12 }} />)}
            </div>
          </div>
        )}
        {!chat.length && !typing && (
          <div className="pt-10 text-center">
            <p className="text-lg font-bold">Ask about your meals</p>
            <p className="mt-1 text-sm text-muted">Every number comes from Avail&apos;s engine, every claim from a paper.</p>
          </div>
        )}
        <div ref={end} />
      </div>

      <div className="sticky bottom-0 z-20 space-y-2 bg-bg px-4 pb-[max(14px,env(safe-area-inset-bottom))] pt-2">
        <div className="no-scrollbar -mx-4 flex gap-2 overflow-x-auto px-4">
          {STARTERS.map((s) => <button key={s} onClick={() => send(s)} className="min-h-10 shrink-0 rounded-full border border-border bg-surface px-3.5 text-sm font-semibold">{s}</button>)}
        </div>
        <form onSubmit={(e) => { e.preventDefault(); send(input); }} className="flex items-center gap-2 rounded-full border border-border bg-surface py-1.5 pl-4 pr-1.5 shadow-card">
          <input value={input} onChange={(e) => setInput(e.target.value)} placeholder="Ask about this meal…" aria-label="Message" className="flex-1 bg-transparent text-[15px] outline-none placeholder:text-faint" />
          <button aria-label="Send" disabled={!input.trim() || typing} className="grid h-10 w-10 place-items-center rounded-full bg-primary text-primary-ink disabled:opacity-40"><SendHorizontal className="h-[18px] w-[18px]" /></button>
        </form>
        <p className="text-center text-[10px] text-faint">Not medical advice. For dosing or symptoms, ask your GP or pharmacist.</p>
      </div>
      <EvidenceSheet id={cite} onClose={() => setCite(null)} />
    </div>
  );
}

export default function ChatPage() {
  return <Suspense><ChatInner /></Suspense>;
}
