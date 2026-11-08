// Same-origin proxy: the browser calls /api/backend/<path>, this route either
//  - answers from the mock backend (API_BASE_URL empty), or
//  - forwards to Person A's FastAPI with the user's Auth0 access token attached.
// Keeping the token server-side means it never touches browser JavaScript.
import { type NextRequest } from "next/server";
import { auth0 } from "@/lib/auth0";
import { mockFetch } from "@/mocks/handler";

export const dynamic = "force-dynamic";

type Ctx = { params: Promise<{ path: string[] }> };

async function handle(req: NextRequest, ctx: Ctx) {
  const { path } = await ctx.params;
  const target = "/" + path.map(encodeURIComponent).join("/");
  const hasBody = !["GET", "HEAD"].includes(req.method);
  const raw = hasBody ? await req.text() : undefined;

  const base = process.env.API_BASE_URL;
  if (!base) {
    let parsed: unknown;
    try { parsed = raw ? JSON.parse(raw) : undefined; } catch { return Response.json({ detail: "Invalid JSON" }, { status: 400 }); }
    return mockFetch(req.method, target, req.nextUrl.searchParams, parsed);
  }

  const headers = new Headers({ "content-type": req.headers.get("content-type") ?? "application/json" });
  if (auth0) {
    try {
      const { token } = await auth0.getAccessToken();
      headers.set("authorization", `Bearer ${token}`);
    } catch {
      // No session: public endpoints still work, protected ones will 401 upstream.
    }
  }
  const upstream = await fetch(`${base.replace(/\/$/, "")}${target}${req.nextUrl.search}`, {
    method: req.method, headers, body: raw, cache: "no-store",
  });
  // Pass the body through as a stream so chat SSE keeps streaming.
  return new Response(upstream.body, {
    status: upstream.status,
    headers: {
      "content-type": upstream.headers.get("content-type") ?? "application/json",
      "cache-control": "no-cache",
    },
  });
}

export { handle as GET, handle as POST, handle as PUT, handle as PATCH, handle as DELETE };
