/* Absorb service worker: install/offline shell + Web Push. Bump VERSION to force an update. */
const VERSION = "absorb-v1";
const OFFLINE_URL = "/offline.html";

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(VERSION).then((c) => c.addAll([OFFLINE_URL, "/icons/icon-192.png"])));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== VERSION).map((k) => caches.delete(k)))).then(() => self.clients.claim()),
  );
});

// Network-first for page navigations, offline page if the network is down.
// API calls and Next.js assets are never cached here (live data only).
self.addEventListener("fetch", (event) => {
  if (event.request.mode !== "navigate") return;
  event.respondWith(fetch(event.request).catch(() => caches.match(OFFLINE_URL)));
});

// Payload sent by Person A's api/alerts/push.py:
// { "title": "Absorb", "body": "...", "url": "/meal/m12", "alert_id": "a7", "type": "conflict" }
self.addEventListener("push", (event) => {
  let data = {};
  try { data = event.data ? event.data.json() : {}; } catch { data = { body: event.data && event.data.text() }; }
  const title = data.title || "Absorb";
  event.waitUntil(
    Promise.all([
      self.registration.showNotification(title, {
        body: data.body || "You have a new iron alert.",
        icon: "/icons/icon-192.png",
        badge: "/icons/badge-72.png",
        tag: data.alert_id || data.type || "absorb",
        data: { url: data.url || "/notifications", alert_id: data.alert_id },
      }),
      // Tell open tabs so the bell badge updates without waiting for the poll.
      self.clients.matchAll({ type: "window" }).then((cs) => cs.forEach((c) => c.postMessage({ type: "alert", payload: data }))),
    ]),
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = (event.notification.data && event.notification.data.url) || "/notifications";
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((wins) => {
      for (const w of wins) {
        if ("focus" in w) { w.navigate(url); return w.focus(); }
      }
      return self.clients.openWindow(url);
    }),
  );
});
