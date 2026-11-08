"use client";
import { Bell, ChevronLeft, History, Home, MessageCircle, Plus, UserRound } from "lucide-react";
import { MotionConfig } from "motion/react";
import { ThemeProvider } from "next-themes";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { Toaster } from "sonner";
import { Drawer } from "vaul";
import { AuthProvider, useAuth } from "@/lib/auth";
import { useStore } from "@/lib/store";
import { cn } from "./ui/primitives";

// ------------------------------------------------------------------ frame
// On desktop the app renders inside a 390 x 844 phone. `transform` on the frame makes every
// position:fixed child (nav, toasts, chat bubble) pin to the phone instead of the browser window.
const FrameCtx = createContext<HTMLElement | null>(null);
export const useFrame = () => useContext(FrameCtx);

function PhoneFrame({ children }: { children: ReactNode }) {
  const [el, setEl] = useState<HTMLDivElement | null>(null);
  return (
    <div className="min-h-dvh sm:grid sm:place-items-center sm:py-8">
      <div className="relative sm:rounded-[54px] sm:bg-[#0f1113] sm:p-[11px] sm:shadow-[0_30px_80px_rgb(0_0_0/0.35)] dark:sm:ring-1 dark:sm:ring-white/10">
        <div ref={setEl} className="relative h-dvh w-full overflow-hidden bg-bg [transform:translateZ(0)] sm:h-[844px] sm:w-[390px] sm:rounded-[44px]">
          <div className="pointer-events-none absolute left-1/2 top-2.5 z-[70] hidden h-[30px] w-[120px] -translate-x-1/2 rounded-full bg-[#0f1113] sm:block" />
          <FrameCtx.Provider value={el}>{el && children}</FrameCtx.Provider>
        </div>
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ providers
export function Providers({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false);
  useEffect(() => {
    try { void Promise.resolve(useStore.persist.rehydrate()).finally(() => setReady(true)); } catch { setReady(true); }
  }, []);
  return (
    <ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
      <MotionConfig reducedMotion="user"><PhoneFrame>{ready ? <AuthProvider>{children}</AuthProvider> : <Splash />}</PhoneFrame></MotionConfig>
    </ThemeProvider>
  );
}

function Splash({ note }: { note?: string }) {
  return (
    <div className="grid h-full place-items-center text-center">
      <div><div className="text-2xl font-extrabold tracking-tight">avail<span className="text-enhancer">.</span></div>
        {note && <p className="mt-2 px-8 text-sm text-muted">{note}</p>}</div>
    </div>
  );
}

// Signed-in gate: every screen except the landing page needs a user; data loads once after sign-in.
const PUBLIC = ["/"];
function Gate({ children }: { children: ReactNode }) {
  const path = usePathname();
  const router = useRouter();
  const { ready, signedIn } = useAuth();
  const loaded = useStore((s) => s.loaded);
  const syncError = useStore((s) => s.syncError);
  const sync = useStore((s) => s.sync);
  const isPublic = PUBLIC.includes(path);
  useEffect(() => { if (ready && !signedIn && !isPublic) router.replace("/"); }, [ready, signedIn, isPublic, router]);
  useEffect(() => { if (ready && signedIn && !loaded) void sync(); }, [ready, signedIn, loaded, sync]);
  if (isPublic) return <>{children}</>;
  if (!ready || !signedIn) return <Splash />;
  if (!loaded) return <Splash note="Loading your meals…" />;
  return (
    <>
      {syncError && <p className="mx-5 mt-2 rounded-xl bg-inhibitor/10 p-3 text-sm text-inhibitor">Couldn&apos;t reach Avail: {syncError}. <button className="font-bold underline" onClick={() => void sync()}>Retry</button></p>}
      {children}
    </>
  );
}

// ------------------------------------------------------------------ chrome
const NO_CHROME = ["/", "/screens", "/permission", "/chat"]; // chat draws its own full-screen bar
const NO_NAV = ["/chat", "/analysing"];
const NO_BUBBLE = ["/add", "/chat", "/analysing", "/confirm"];

export function Chrome({ children }: { children: ReactNode }) {
  const path = usePathname();
  const bare = NO_CHROME.includes(path);
  const nav = !bare && !NO_NAV.includes(path);
  return (
    <div className="no-scrollbar relative h-full overflow-y-auto overscroll-contain" id="scroller">
      {!bare && path !== "/chat" && <Header />}
      <main className={cn(bare ? "" : "px-5 pt-2", nav ? "pb-32" : "pb-8")}><Gate>{children}</Gate></main>
      {nav && <BottomNav path={path} />}
      {nav && !NO_BUBBLE.includes(path) && <ChatBubble />}
      <Toaster position="top-center" offset={14} gap={8} toastOptions={{ classNames: {
        toast: "!rounded-2xl !border !border-border !bg-surface !text-ink !shadow-card !font-sans",
        description: "!text-muted", actionButton: "!bg-primary !text-primary-ink !font-bold !rounded-lg" } }} />
    </div>
  );
}

function Header() {
  const unread = useStore((s) => s.alerts.some((a) => !a.read));
  return (
    <header className="sticky top-0 z-30 flex h-[68px] items-end justify-between bg-bg/90 px-5 pb-2 backdrop-blur-md sm:h-[84px]">
      <Link href="/home" className="text-[25px] font-extrabold tracking-[-0.06em]">avail<span className="text-enhancer">.</span></Link>
      <Link href="/notifications" aria-label={unread ? "Notifications, unread" : "Notifications"}
        className="relative grid h-11 w-11 place-items-center rounded-full border border-border bg-surface">
        <Bell className="h-5 w-5" strokeWidth={1.8} />
        {unread && <span className="absolute right-2.5 top-2.5 h-2.5 w-2.5 rounded-full bg-inhibitor ring-2 ring-surface" />}
      </Link>
    </header>
  );
}

function AbsorbIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={className} aria-hidden>
      <path d="M5 17.5c3.3 0 4.2-3 5.3-6.3C11.5 7.7 13 5 18.8 5" stroke="currentColor" strokeLinecap="round" strokeWidth="1.8" />
      <path d="m15.5 2.8 3.7 2.1-2.5 3.5M5 14v3.5h3.5" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" />
    </svg>
  );
}

function BottomNav({ path }: { path: string }) {
  const tab = (href: string, label: string, Icon: (p: { className?: string }) => ReactNode, also: string[] = []) => {
    const active = path === href || also.some((a) => path.startsWith(a));
    return (
      <Link href={href} className={cn("flex h-[60px] flex-col items-center justify-center gap-1 text-[10px] font-semibold", active ? "text-primary" : "text-faint")}>
        <Icon className="h-[22px] w-[22px]" />{label}
      </Link>
    );
  };
  return (
    <nav className="fixed inset-x-0 bottom-0 z-40 grid h-[84px] grid-cols-5 items-start border-t border-border bg-[var(--nav)] px-2 pt-1.5 pb-[max(8px,env(safe-area-inset-bottom))] backdrop-blur-md">
      {tab("/home", "Home", (p) => <Home {...p} strokeWidth={1.8} />)}
      {tab("/absorb", "Absorb", AbsorbIcon, ["/absorb", "/fix"])}
      <Link href="/add" aria-label="Add meal" className="relative -top-5 flex flex-col items-center gap-1 text-[10px] font-semibold text-muted">
        <span className={cn("grid h-[58px] w-[58px] place-items-center rounded-full border-[5px] border-bg bg-primary text-primary-ink shadow-[0_8px_20px_color-mix(in_oklab,var(--primary)_35%,transparent)] transition-transform active:scale-95", (path === "/add" || path === "/confirm") && "ring-2 ring-primary/30")}>
          <Plus className="h-7 w-7" strokeWidth={2.2} />
        </span>
        Add meal
      </Link>
      {tab("/history", "History", (p) => <History {...p} strokeWidth={1.8} />)}
      {tab("/you", "You", (p) => <UserRound {...p} strokeWidth={1.8} />, ["/you", "/reminder"])}
    </nav>
  );
}

function ChatBubble() {
  return (
    <Link href="/chat" aria-label="Ask Avail" className="fixed bottom-[96px] left-4 z-40 grid h-12 w-12 place-items-center rounded-full bg-iron text-iron-ink shadow-[0_8px_20px_rgb(0_0_0/0.22)] transition-transform active:scale-95">
      <MessageCircle className="h-[22px] w-[22px]" strokeWidth={1.8} />
    </Link>
  );
}

export function BackBar({ title, href }: { title?: string; href?: string }) {
  const router = useRouter();
  return (
    <div className="mb-3 flex items-center gap-2">
      <button onClick={() => (href ? router.push(href) : router.back())} className="-ml-2 flex h-11 items-center gap-1 rounded-xl px-2 text-sm font-semibold text-muted hover:bg-surface-2">
        <ChevronLeft className="h-5 w-5" />Back
      </button>
      {title && <span className="text-sm font-semibold">{title}</span>}
    </div>
  );
}

// ------------------------------------------------------------------ bottom sheet (vaul), rendered inside the phone
export function Sheet({ open, onOpenChange, title, children }: { open: boolean; onOpenChange: (o: boolean) => void; title: string; children: ReactNode }) {
  const frame = useFrame();
  return (
    <Drawer.Root open={open} onOpenChange={onOpenChange}>
      <Drawer.Portal container={frame}>
        <Drawer.Overlay className="fixed inset-0 z-[80] bg-black/45" />
        <Drawer.Content className="fixed inset-x-0 bottom-0 z-[90] mt-24 flex max-h-[88%] flex-col rounded-t-[28px] bg-surface outline-none">
          <div className="mx-auto mt-3 h-1.5 w-10 shrink-0 rounded-full bg-surface-3" />
          <Drawer.Title className="sr-only">{title}</Drawer.Title>
          <div className="overflow-y-auto px-5 pt-4 pb-[max(20px,env(safe-area-inset-bottom))]">{children}</div>
        </Drawer.Content>
      </Drawer.Portal>
    </Drawer.Root>
  );
}
