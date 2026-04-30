/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Required so the prod Dockerfile can ship a self-contained `server.js`.
  output: 'standalone',
  // The frontend talks to the backend directly via axios using
  // NEXT_PUBLIC_API_URL — no rewrites are needed. Earlier versions of this
  // config rewrote /api/* → /v1/* through Next, which would have collided
  // with the new /api/search and /api/similar endpoints living on the
  // backend. Removed to avoid that future foot-gun.
};

module.exports = nextConfig;
