"use client";
// PWA + Web Push helpers. The service worker lives in public/sw.js.

export function pushSupport(): { supported: boolean; reason?: string } {
  if (typeof window === "undefined") return { supported: false };
  if (!("serviceWorker" in navigator)) return { supported: false, reason: "This browser has no service workers." };
  if (!("PushManager" in globalThis)) {
    const ios = /iphone|ipad|ipod/i.test(navigator.userAgent);
    const standalone = window.matchMedia("(display-mode: standalone)").matches;
    if (ios && !standalone) return { supported: false, reason: "On iPhone, tap Share → Add to Home Screen, then open Absorb from the home screen to enable push." };
    return { supported: false, reason: "This browser does not support push notifications." };
  }
  return { supported: true };
}

export async function registerServiceWorker() {
  if (typeof window === "undefined" || !("serviceWorker" in navigator)) return null;
  try {
    return await navigator.serviceWorker.register("/sw.js", { scope: "/" });
  } catch (e) {
    console.warn("SW registration failed", e);
    return null;
  }
}

function urlBase64ToUint8Array(base64: string) {
  const padding = "=".repeat((4 - (base64.length % 4)) % 4);
  const b64 = (base64 + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(b64);
  return Uint8Array.from([...raw].map((c) => c.charCodeAt(0)));
}

/** Ask permission and return the subscription JSON to PUT into /alerts/preferences. */
export async function subscribeToPush(): Promise<PushSubscriptionJSON> {
  const key = process.env.NEXT_PUBLIC_VAPID_PUBLIC_KEY;
  if (!key) throw new Error("NEXT_PUBLIC_VAPID_PUBLIC_KEY is not set. Ask Person A for the VAPID public key.");
  const perm = await Notification.requestPermission();
  if (perm !== "granted") throw new Error("Notifications were blocked. Enable them in your browser settings.");
  const reg = (await navigator.serviceWorker.getRegistration()) ?? (await registerServiceWorker());
  if (!reg) throw new Error("Service worker is not registered.");
  await navigator.serviceWorker.ready;
  const existing = await reg.pushManager.getSubscription();
  const sub = existing ?? (await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: urlBase64ToUint8Array(key) }));
  return sub.toJSON();
}

export async function unsubscribeFromPush() {
  const reg = await navigator.serviceWorker.getRegistration();
  const sub = await reg?.pushManager.getSubscription();
  await sub?.unsubscribe();
}

/** Local notification through the SW. A demo fallback that needs no server. */
export async function showLocalNotification(title: string, body: string, url = "/notifications") {
  if (Notification.permission !== "granted") await Notification.requestPermission();
  const reg = await navigator.serviceWorker.getRegistration();
  if (reg) await reg.showNotification(title, { body, icon: "/icons/icon-192.png", badge: "/icons/badge-72.png", data: { url } });
}
