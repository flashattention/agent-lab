"use client";

import { Group, Panel, Separator } from "react-resizable-panels";
import { cn } from "@/lib/utils";

export { Group as SplitGroup, Panel as SplitPanel };

export function SplitHandle({ vertical = false, className }: { vertical?: boolean; className?: string }) {
  return (
    <Separator
      className={cn(
        "group relative shrink-0 bg-border transition-colors data-[separator=active]:bg-accent data-[separator=hover]:bg-accent/60",
        vertical ? "h-px w-full" : "h-full w-px",
        className,
      )}
    >
      <span className={cn("absolute", vertical ? "inset-x-0 -inset-y-1.5" : "-inset-x-1.5 inset-y-0")} />
    </Separator>
  );
}
