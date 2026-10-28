"use client";

import { useEffect, useId, useState } from "react";
import { useTheme } from "next-themes";

let initializedTheme: string | null = null;

export function Mermaid({ chart }: { chart: string }) {
  const id = useId().replace(/[^a-zA-Z0-9]/g, "");
  const { resolvedTheme } = useTheme();
  const [svg, setSvg] = useState<string>("");
  const [error, setError] = useState<string>("");

  useEffect(() => {
    let alive = true;
    (async () => {
      const mermaid = (await import("mermaid")).default;
      const theme = resolvedTheme === "dark" ? "dark" : "neutral";
      if (initializedTheme !== theme) {
        mermaid.initialize({
          startOnLoad: false,
          theme,
          securityLevel: "strict",
          fontFamily: "Pretendard Variable, Pretendard, system-ui, sans-serif",
          themeVariables: resolvedTheme === "dark" ? { primaryColor: "#1e1b3a", lineColor: "#6b6b78" } : {},
        });
        initializedTheme = theme;
      }
      try {
        const { svg } = await mermaid.render(`m${id}${theme}`, chart);
        if (alive) {
          setSvg(svg);
          setError("");
        }
      } catch (e) {
        if (alive) setError((e as Error).message);
      }
    })();
    return () => {
      alive = false;
    };
  }, [chart, id, resolvedTheme]);

  if (error)
    return (
      <pre className="text-xs">
        <code>{chart}</code>
      </pre>
    );
  return (
    <div
      className="my-5 flex justify-center overflow-x-auto rounded-xl border border-border bg-surface p-4 [&_svg]:max-w-full"
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  );
}
