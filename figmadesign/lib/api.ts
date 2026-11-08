// Thin client for the Absorb API. Every request goes to /api/* (proxied to FastAPI by next.config.ts)
// with the signed-in user's access token.

type TokenGetter = () => Promise<string | null>;
let getToken: TokenGetter = async () => null;
export const setTokenGetter = (fn: TokenGetter) => { getToken = fn; };

const BASE = "/api";

export class ApiError extends Error {
  constructor(public status: number, message: string, public body?: unknown) { super(message); }
}

async function request<T>(method: string, path: string, body?: unknown, init: RequestInit = {}): Promise<T> {
  const token = await getToken();
  const headers: Record<string, string> = { ...(init.headers as Record<string, string>) };
  if (token) headers.Authorization = `Bearer ${token}`;
  let payload: BodyInit | undefined;
  if (body instanceof FormData) payload = body;
  else if (body !== undefined) { headers["Content-Type"] = "application/json"; payload = JSON.stringify(body); }
  const res = await fetch(`${BASE}${path}`, { ...init, method, headers, body: payload });
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  let data: any;   // eslint-disable-line @typescript-eslint/no-explicit-any
  try { data = text ? JSON.parse(text) : undefined; } catch { data = { detail: res.status >= 500 ? "The server had a problem. Please try again." : text }; }
  if (!res.ok) {
    const detail = (data && (data.detail?.toString?.() ?? data.detail)) || res.statusText;
    throw new ApiError(res.status, typeof detail === "string" ? detail : JSON.stringify(detail), data);
  }
  return data as T;
}

export const api = {
  get: <T>(path: string) => request<T>("GET", path),
  post: <T>(path: string, body?: unknown) => request<T>("POST", path, body),
  put: <T>(path: string, body?: unknown) => request<T>("PUT", path, body),
  patch: <T>(path: string, body?: unknown) => request<T>("PATCH", path, body),
  del: <T>(path: string) => request<T>("DELETE", path),
};

/** data: URL (from the photo picker) → Blob for multipart upload. */
export async function dataUrlToBlob(dataUrl: string): Promise<Blob> {
  return (await fetch(dataUrl)).blob();
}
