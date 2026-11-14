"use client";

import { useEffect } from "react";
import { ThemeProvider } from "next-themes";
import { startAuth } from "@/lib/auth";

export function Providers({ children }: { children: React.ReactNode }) {
  useEffect(() => startAuth(), []);
  return (
    <ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
      {children}
    </ThemeProvider>
  );
}
