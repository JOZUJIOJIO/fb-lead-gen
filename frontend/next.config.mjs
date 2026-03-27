/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  typescript: { ignoreBuildErrors: true },
  eslint: { ignoreDuringBuilds: true },
  async rewrites() {
    const backendUrl = process.env.BACKEND_URL || "http://localhost:8000";
    const automationUrl = process.env.AUTOMATION_URL || "http://localhost:3001";
    return [
      {
        source: "/automation/:path*",
        destination: `${automationUrl}/:path*`,
      },
      {
        source: "/api/:path*",
        destination: `${backendUrl}/:path*`,
      },
    ];
  },
};

export default nextConfig;
