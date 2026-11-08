"use client";
// Sign-in. Auth0 when NEXT_PUBLIC_AUTH0_CLIENT_ID is set; otherwise a local dev login (backend /auth/dev-token,
// which only exists while AUTH_DEV_SECRET is set in backend/.env). The access token goes on every API call.
import { Auth0Provider, useAuth0 } from "@auth0/auth0-react";
import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { setTokenGetter } from "./api";

const DOMAIN = process.env.NEXT_PUBLIC_AUTH0_DOMAIN ?? "";
const CLIENT_ID = process.env.NEXT_PUBLIC_AUTH0_CLIENT_ID ?? "";
const AUDIENCE = process.env.NEXT_PUBLIC_AUTH0_AUDIENCE ?? "";
export const AUTH_MODE: "auth0" | "dev" = CLIENT_ID ? "auth0" : "dev";

type AuthState = { ready: boolean; signedIn: boolean; name: string | null; login: () => void; logout: () => void; error: string | null };
const AuthCtx = createContext<AuthState>({ ready: false, signedIn: false, name: null, login: () => {}, logout: () => {}, error: null });
export const useAuth = () => useContext(AuthCtx);

function Auth0Bridge({ children }: { children: ReactNode }) {
  const { isLoading, isAuthenticated, user, error, getAccessTokenSilently, loginWithRedirect, logout } = useAuth0();
  useEffect(() => {
    setTokenGetter(async () => (isAuthenticated ? (await getAccessTokenSilently()) ?? null : null));
  }, [isAuthenticated, getAccessTokenSilently]);
  const value = useMemo<AuthState>(() => ({
    ready: !isLoading, signedIn: isAuthenticated, name: user?.given_name ?? user?.name ?? user?.nickname ?? null,
    error: error?.message ?? null,
    login: () => void loginWithRedirect({ appState: { returnTo: "/home" } }),
    logout: () => void logout({ logoutParams: { returnTo: window.location.origin } }),
  }), [isLoading, isAuthenticated, user, error, loginWithRedirect, logout]);
  return <AuthCtx.Provider value={value}>{children}</AuthCtx.Provider>;
}

const DEV_KEY = "avail-dev-token";
function DevBridge({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { try { setToken(localStorage.getItem(DEV_KEY)); } catch { /* private mode */ } setReady(true); }, []);
  useEffect(() => { setTokenGetter(async () => token); }, [token]);
  const value = useMemo<AuthState>(() => ({
    ready, signedIn: !!token, name: null, error,
    login: () => {
      fetch("/api/auth/dev-token?name=demo").then(async (r) => {
        if (!r.ok) throw new Error("Dev login is off. Set NEXT_PUBLIC_AUTH0_CLIENT_ID, or AUTH_DEV_SECRET on the backend.");
        const { access_token } = await r.json();
        try { localStorage.setItem(DEV_KEY, access_token); } catch { /* ignore */ }
        setToken(access_token);
        window.location.assign("/home");
      }).catch((e) => setError(e.message));
    },
    logout: () => { try { localStorage.removeItem(DEV_KEY); } catch { /* ignore */ } setToken(null); window.location.assign("/"); },
  }), [ready, token, error]);
  return <AuthCtx.Provider value={value}>{children}</AuthCtx.Provider>;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [origin, setOrigin] = useState<string | null>(null);
  useEffect(() => setOrigin(window.location.origin), []);
  if (!origin) return null;   // Auth0 needs the browser (window, crypto); render after mount
  if (AUTH_MODE === "dev") return <DevBridge>{children}</DevBridge>;
  return (
    <Auth0Provider domain={DOMAIN} clientId={CLIENT_ID} cacheLocation="localstorage"
      authorizationParams={{ audience: AUDIENCE, redirect_uri: origin, scope: "openid profile email" }}
      onRedirectCallback={(appState) => window.history.replaceState({}, "", appState?.returnTo ?? "/home")}>
      <Auth0Bridge>{children}</Auth0Bridge>
    </Auth0Provider>
  );
}
