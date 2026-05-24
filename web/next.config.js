/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Keep dev artifacts separate from production build artifacts.
  // This avoids MODULE_NOT_FOUND chunk errors when running dev and build workflows interchangeably.
  distDir: process.env.NODE_ENV === "development" ? ".next-dev" : ".next",
};

module.exports = nextConfig;
