import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // The dashboard only talks to the local FastAPI backend (NEXT_PUBLIC_API_URL).
  // No secrets are read here: anything NEXT_PUBLIC_* is shipped to the browser.
  poweredByHeader: false,
};

export default nextConfig;
