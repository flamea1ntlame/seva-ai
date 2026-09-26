/** @type {import('next').NextConfig} */
const { resolveBackendUrl } = require("./src/lib/backendConfig");

const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    const backendUrl = resolveBackendUrl();
    return [
      {
        source: "/api/:path*",
        destination: `${backendUrl}/api/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
