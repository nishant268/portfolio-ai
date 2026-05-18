import type { NextConfig } from "next";

const isProd = process.env.NODE_ENV === "production";

const nextConfig: NextConfig = {
  // Standalone output: self-contained Node.js server for Render deployment
  output: isProd ? "standalone" : undefined,
  // Allow dev origins in local development
  allowedDevOrigins: ["127.0.0.1", "localhost"],
};

export default nextConfig;
