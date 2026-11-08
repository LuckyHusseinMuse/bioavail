import { Auth0Client } from "@auth0/nextjs-auth0/server";

/** Demo mode = no AUTH0_DOMAIN set. The app runs with a fake demo user. */
export const authEnabled = Boolean(process.env.AUTH0_DOMAIN);

export const auth0 = authEnabled
  ? new Auth0Client({
      authorizationParameters: {
        // The audience makes Auth0 issue a JWT access token that FastAPI can validate.
        audience: process.env.AUTH0_AUDIENCE,
        scope: "openid profile email offline_access",
      },
    })
  : null;

export type SessionUser = { name: string; email?: string; picture?: string; sub: string };

export async function getUser(): Promise<SessionUser | null> {
  if (!auth0) return { name: "Demo user", email: "demo@absorb.app", sub: "demo|1" };
  const session = await auth0.getSession();
  if (!session) return null;
  const u = session.user;
  return { name: u.name ?? u.email ?? "You", email: u.email, picture: u.picture, sub: u.sub };
}
