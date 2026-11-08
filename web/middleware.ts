import { NextResponse, type NextRequest } from "next/server";
import { auth0 } from "@/lib/auth0";

// Pages that need a signed-in user. /interactions and /validation stay public for judges.
const PROTECTED = ["/log", "/meal", "/today", "/chat", "/notifications", "/settings", "/profile"];
// Backend paths that work without login (the public demo pages use them).
const PUBLIC_API = ["/api/backend/engine/", "/api/backend/eval/", "/api/backend/evidence/", "/api/backend/foods"];

export async function middleware(req: NextRequest) {
  if (!auth0) return NextResponse.next(); // demo mode

  // Mounts /auth/login, /auth/logout, /auth/callback, /auth/profile and rolls the session.
  const authRes = await auth0.middleware(req);
  const { pathname } = req.nextUrl;
  if (pathname.startsWith("/auth")) return authRes;

  const needsPage = PROTECTED.some((p) => pathname === p || pathname.startsWith(p + "/"));
  const needsApi = pathname.startsWith("/api/backend/") && !PUBLIC_API.some((p) => pathname.startsWith(p));
  if (needsPage || needsApi) {
    const session = await auth0.getSession(req);
    if (!session) {
      if (needsApi) return NextResponse.json({ detail: "Not signed in" }, { status: 401 });
      return NextResponse.redirect(new URL(`/auth/login?returnTo=${encodeURIComponent(pathname)}`, req.nextUrl.origin));
    }
  }
  return authRes;
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|sw.js|manifest.webmanifest|icons/|demo/).*)"],
};
