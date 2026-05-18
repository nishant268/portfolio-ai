import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: process.env.RENDER ? "export" : "standalone",
  allowedDevOrigins: ["127.0.0.1", "localhost"],
  // Required for static export — disable image optimization (no server)
  images: { unoptimized: true },
};

export default nextConfig;
