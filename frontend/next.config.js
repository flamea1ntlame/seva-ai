/** @type {import('next').NextConfig} */
const path = require("path");
const { resolveBackendUrl } = require(path.join(__dirname, "src/lib/backendConfig"));

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
