"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import type { Alert } from "@/lib/types";
import { useApi } from "@/lib/api";
import { registerServiceWorker } from "@/lib/push";
import { IconBell, IconChat, IconGraph, IconHome, IconPlus, IconUser, IconX } from "./Icons";

type User = { name: string; picture?: string } | null;

/** Fire this after anything that may create alerts (e.g. saving a meal). */
export const notifyAlertsChanged = () => window.dispatchEvent(new Event("absorb:alerts-changed"));

export default function AppShell({ user, demoMode, children }: { user: User; demoMode: boolean; children: React.ReactNode }) {
  const path = usePathname();
  const signedIn = !!user;
  const { data: alerts, reload } = useApi<Alert[]>(signedIn ? "/alerts" : null, { refreshMs: 20000 });
  const unread = alerts?.filter((a) => !a.read_at).length ?? 0;

  // Toasts for alerts that arrive while the app is open (the fallback when push is unavailable).
  const seen = useRef<Set<string> | null>(null);
  const [toasts, setToasts] = useState<Alert[]>([]);
  useEffect(() => {
    if (!alerts) return;
    if (!seen.current) { seen.current = new Set(alerts.map((a) => a.id)); return; }
    const fresh = alerts.filter((a) => !seen.current!.has(a.id));
    fresh.forEach((a) => seen.current!.add(a.id));
    if (fresh.length) setToasts((t) => [...fresh, ...t].slice(0, 3));
  }, [alerts]);
  useEffect(() => {
    if (!toasts.length) return;
    const t = setTimeout(() => setToasts((x) => x.slice(0, -1)), 7000);
    return () => clearTimeout(t);
  }, [toasts]);

  // Refresh immediately when a push arrives or another page changes alerts.
  useEffect(() => {
    registerServiceWorker();
    const onMsg = (e: MessageEvent) => { if (e.data?.type === "alert") reload(); };
    const onLocal = () => reload();
    navigator.serviceWorker?.addEventListener("message", onMsg);
    window.addEventListener("absorb:alerts-changed", onLocal);
    return () => {
      navigator.serviceWorker?.removeEventListener("message", onMsg);
      window.removeEventListener("absorb:alerts-changed", onLocal);
    };
  }, [reload]);

  const nav = [
    { href: "/today", label: "Today", icon: IconHome },
    { href: "/log", label: "Log", icon: IconPlus },
    { href: "/chat", label: "Ask", icon: IconChat },
    { href: "/interactions", label: "Map", icon: IconGraph },
    { href: "/profile", label: "Me", icon: IconUser },
  ];
  const hideChrome = path === "/";

  return (
    <div className="min-h-dvh flex flex-col">
      {demoMode && (
        <div className="bg-warning/25 text-ink text-xs text-center py-1 px-4">Demo mode: Auth0 is not configured, so you're signed in as a demo user</div>
      )}
      {!hideChrome && (
        <header className="sticky top-0 z-30 bg-bg/90 backdrop-blur border-b border-border">
          <div className="mx-auto max-w-xl flex items-center justify-between px-4 h-14">
            <Link href={signedIn ? "/today" : "/"} className="font-bold text-lg tracking-tight">Absorb</Link>
            {signedIn ? (
              <div className="flex items-center gap-1">
                <Link href="/notifications" className="relative p-2.5 rounded-full hover:bg-surface-2" aria-label={`Notifications, ${unread} unread`}>
                  <IconBell />
                  {unread > 0 && (
                    <span className="absolute top-1 right-1 min-w-5 h-5 px-1 rounded-full bg-critical text-white text-[11px] font-bold grid place-items-center tabular">{unread}</span>
                  )}
                </Link>
                <Link href="/profile" className="p-1" aria-label="Profile">
                  {user?.picture ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={user.picture} alt="" className="w-8 h-8 rounded-full" />
                  ) : (
                    <span className="w-8 h-8 rounded-full bg-brand text-white grid place-items-center text-sm font-bold">{user?.name?.[0] ?? "?"}</span>
                  )}
                </Link>
              </div>
            ) : (
              <a href="/auth/login" className="btn btn-primary !py-1.5 !min-h-0 text-sm">Sign in</a>
            )}
          </div>
        </header>
      )}

      <main className={`flex-1 mx-auto w-full max-w-xl px-4 ${hideChrome ? "" : "pt-4 pb-28"}`}>{children}</main>

      <div className="fixed top-16 inset-x-0 z-50 flex flex-col items-center gap-2 px-4 pointer-events-none" aria-live="polite">
        {toasts.map((t) => (
          <div key={t.id} className="pointer-events-auto card shadow-lg w-full max-w-md p-3 flex gap-3 items-start">
            <span className={`mt-1.5 w-2 h-2 rounded-full shrink-0 ${t.type === "conflict" ? "bg-critical" : t.type === "data_gap" ? "bg-warning" : "bg-brand"}`} />
            <Link href={t.meal_id ? `/meal/${t.meal_id}` : "/notifications"} className="text-sm flex-1">{t.message}</Link>
            <button onClick={() => setToasts((x) => x.filter((y) => y.id !== t.id))} aria-label="Dismiss" className="text-muted">
              <IconX className="w-4 h-4" />
            </button>
          </div>
        ))}
      </div>

      {signedIn && !hideChrome && path !== "/chat" && (
        <Link href="/chat" aria-label="Ask about your iron" className="fixed z-40 right-4 bottom-24 w-14 h-14 rounded-full bg-brand text-white shadow-lg grid place-items-center">
          <IconChat />
        </Link>
      )}

      {!hideChrome && (
        <nav className="fixed bottom-0 inset-x-0 z-40 bg-surface border-t border-border pb-[env(safe-area-inset-bottom)]">
          <div className="mx-auto max-w-xl grid grid-cols-5">
            {nav.map(({ href, label, icon: Icon }) => {
              const active = path === href || path.startsWith(href + "/");
              return (
                <Link key={href} href={href} className={`flex flex-col items-center gap-0.5 py-2 text-[11px] ${active ? "text-brand font-semibold" : "text-muted"}`}>
                  <Icon className="w-6 h-6" />
                  {label}
                </Link>
              );
            })}
          </div>
        </nav>
      )}
    </div>
  );
}
