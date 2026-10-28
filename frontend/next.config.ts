import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Docker 배포용 최소 런타임 번들 (.next/standalone)
  output: "standalone",
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
