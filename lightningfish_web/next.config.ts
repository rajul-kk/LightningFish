import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/py/:path*",
        destination: `${process.env.PYTHON_SERVICE_URL}/:path*`,
      },
    ];
  },
};

export default nextConfig;
