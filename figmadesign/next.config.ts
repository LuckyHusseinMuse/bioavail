import type { NextConfig } from "next";

// The browser always calls /api/...; Next forwards it to the FastAPI backend. One origin means no CORS,
// and a single HTTPS tunnel (or one domain on Vultr) serves both the app and the API.
const BACKEND_URL = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${BACKEND_URL}/:path*` }];
  },
  // Lets phones load the dev server through a Cloudflare quick tunnel.
  allowedDevOrigins: ["*.trycloudflare.com"],
  // AI calls (photo recognition, chat with tools, rate-limit retries) can take longer than the 30 s default.
  experimental: { proxyTimeout: 120_000 },
};

export default nextConfig;
