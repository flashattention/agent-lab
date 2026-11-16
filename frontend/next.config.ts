import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Docker 배포용 최소 런타임 번들 (.next/standalone)
  output: "standalone",
  cacheComponents: true,
  partialPrefetching: true,
  // 보안 헤더 (docs/PRODUCTION_READINESS.md S7). CSP 는 Monaco/Mermaid/Supabase 출처를 정리한 뒤 별도로 도입한다.
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "X-Frame-Options", value: "DENY" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), payment=(), usb=()" },
          { key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains" },
        ],
      },
    ];
  },
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
