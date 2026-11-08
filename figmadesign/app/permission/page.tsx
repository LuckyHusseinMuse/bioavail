"use client";
// SCREEN 17: Permission priming (asked before the browser's own prompt)
import { BellRing } from "lucide-react";
import { motion } from "motion/react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/primitives";

function PermissionInner() {
  const router = useRouter();
  const next = useSearchParams().get("next") || "/home";
  const [busy, setBusy] = useState(false);

  async function allow() {
    setBusy(true);
    try {
      if (typeof Notification === "undefined") {
        toast("This browser can't show notifications", { description: "On iPhone, add Avail to your home screen first." });
      } else {
        const p = await Notification.requestPermission();
        if (p === "granted") toast.success("Notifications on");
        else toast("Notifications are off", { description: "You can turn them on in your browser settings." });
      }
    } finally {
      setBusy(false);
      router.replace(next);
    }
  }

  return (
    <div className="flex min-h-dvh flex-col px-7 pb-10 pt-24 text-center sm:min-h-[844px]">
      <div className="flex flex-1 flex-col items-center justify-center">
        <div className="relative">
          <motion.span className="absolute inset-0 rounded-full bg-primary/20" animate={{ scale: [1, 1.5], opacity: [0.6, 0] }} transition={{ duration: 1.8, repeat: Infinity }} />
          <motion.span initial={{ rotate: -12 }} animate={{ rotate: [0, -14, 12, -8, 0] }} transition={{ duration: 1.2, delay: 0.4 }}
            className="relative grid h-24 w-24 place-items-center rounded-full bg-primary text-primary-ink shadow-[0_12px_30px_color-mix(in_oklab,var(--primary)_40%,transparent)]">
            <BellRing className="h-11 w-11" />
          </motion.span>
        </div>
        <h1 className="mt-8 text-2xl font-extrabold tracking-tight">Stay on time</h1>
        <p className="mt-3 text-[15px] leading-relaxed text-muted">Avail needs permission to send reminders. You can turn this off any time.</p>
      </div>
      <div className="space-y-2">
        <Button size="lg" className="w-full" onClick={allow} disabled={busy}>Allow notifications</Button>
        <Button variant="ghost" className="w-full" onClick={() => router.replace(next)}>Not now</Button>
      </div>
    </div>
  );
}

export default function PermissionPage() {
  return <Suspense><PermissionInner /></Suspense>;
}
