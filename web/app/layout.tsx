import type { Metadata, Viewport } from "next";
import "./globals.css";
import AppShell from "@/components/AppShell";
import { authEnabled, getUser } from "@/lib/auth0";

export const metadata: Metadata = {
  title: "Absorb",
  description: "What you eat is not what you absorb. See how your meals change the iron you actually absorb.",
  appleWebApp: { capable: true, title: "Absorb", statusBarStyle: "default" },
  icons: { icon: "/icons/icon-192.png", apple: "/icons/apple-touch-icon.png" },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f6f5f2" },
    { media: "(prefers-color-scheme: dark)", color: "#111110" },
  ],
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const user = await getUser();
  return (
    <html lang="en">
      <body>
        <AppShell user={user} demoMode={!authEnabled}>
          {children}
        </AppShell>
      </body>
    </html>
  );
}
