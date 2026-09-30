import type { NextConfig } from "next";

if (process.env.VERCEL === "1") {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL;
  let valid = false;
  try {
    const parsed = new URL(apiUrl ?? "");
    valid = parsed.protocol === "https:" && !parsed.username && !parsed.password
      && parsed.pathname === "/" && !parsed.search && !parsed.hash
      && parsed.hostname !== "localhost" && parsed.hostname !== "127.0.0.1";
  } catch {
    valid = false;
  }
  if (!valid) {
    throw new Error("Set NEXT_PUBLIC_API_URL to the public HTTPS API origin for Vercel builds.");
  }
}

const nextConfig: NextConfig = {
  /* config options here */
};

export default nextConfig;
