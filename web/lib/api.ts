"use client";
// Browser-side API helpers. Everything goes through the same-origin proxy at
// /api/backend, which handles mocks vs real backend and attaches the Auth0 token.
import { useCallback, useEffect, useRef, useState } from "react";
import type { ChatEvent } from "./types";

const BASE = "/api/backend";

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(BASE + path, {
    method,
    headers: body !== undefined ? { "content-type": "application/json" } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
    cache: "no-store",
  });
  if (!res.ok) {
    let msg = res.statusText;
    try { const j = await res.json(); msg = j.detail ?? msg; } catch {}
    if (res.status === 401 && typeof window !== "undefined") window.location.href = `/auth/login?returnTo=${encodeURIComponent(location.pathname)}`;
    throw new ApiError(res.status, typeof msg === "string" ? msg : JSON.stringify(msg));
  }
  return res.status === 204 ? (undefined as T) : res.json();
}

export const api = {
  get: <T,>(p: string) => request<T>("GET", p),
  post: <T,>(p: string, b?: unknown) => request<T>("POST", p, b ?? {}),
  put: <T,>(p: string, b: unknown) => request<T>("PUT", p, b),
  patch: <T,>(p: string, b: unknown) => request<T>("PATCH", p, b),
};

/** Tiny SWR-like hook: { data, error, loading, reload, setData } */
export function useApi<T>(path: string | null, opts: { refreshMs?: number } = {}) {
  const [data, setData] = useState<T | undefined>();
  const [error, setError] = useState<Error | undefined>();
  const [loading, setLoading] = useState(!!path);
  const alive = useRef(true);

  const reload = useCallback(async () => {
    if (!path) return;
    try {
      const d = await api.get<T>(path);
      if (alive.current) { setData(d); setError(undefined); }
    } catch (e) {
      if (alive.current) setError(e as Error);
    } finally {
      if (alive.current) setLoading(false);
    }
  }, [path]);

  useEffect(() => {
    alive.current = true;
    setLoading(!!path);
    reload();
    if (!opts.refreshMs) return () => { alive.current = false; };
    const t = setInterval(reload, opts.refreshMs);
    return () => { alive.current = false; clearInterval(t); };
  }, [reload, opts.refreshMs, path]);

  return { data, error, loading, reload, setData };
}

/** POST /chat and parse the Server-Sent Events stream. */
export async function streamChat(message: string, onEvent: (e: ChatEvent) => void, signal?: AbortSignal) {
  const res = await fetch(`${BASE}/chat`, {
    method: "POST",
    headers: { "content-type": "application/json", accept: "text/event-stream" },
    body: JSON.stringify({ message }),
    signal,
  });
  if (!res.ok || !res.body) { onEvent({ type: "error", message: `Chat failed (${res.status})` }); return; }
  const reader = res.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let idx;
    while ((idx = buf.indexOf("\n\n")) >= 0) {
      const chunk = buf.slice(0, idx);
      buf = buf.slice(idx + 2);
      const line = chunk.split("\n").find((l) => l.startsWith("data:"));
      if (!line) continue;
      try { onEvent(JSON.parse(line.slice(5).trim())); } catch { /* ignore keep-alives */ }
    }
  }
}

/** Shrink a photo before upload: phones produce 4-12 MB images, Gemini only needs ~1024 px. */
export async function fileToJpegBase64(file: File, maxSide = 1024): Promise<{ base64: string; mime: string; previewUrl: string }> {
  const bmp = await createImageBitmap(file);
  const scale = Math.min(1, maxSide / Math.max(bmp.width, bmp.height));
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(bmp.width * scale);
  canvas.height = Math.round(bmp.height * scale);
  canvas.getContext("2d")!.drawImage(bmp, 0, 0, canvas.width, canvas.height);
  const dataUrl = canvas.toDataURL("image/jpeg", 0.85);
  return { base64: dataUrl.split(",")[1], mime: "image/jpeg", previewUrl: dataUrl };
}
