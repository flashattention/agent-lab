"use client";

import { DynamicIcon, iconNames, type IconName } from "lucide-react/dynamic";

const known = new Set<string>(iconNames);

/** 콘텐츠 JSON 의 아이콘 이름("BookOpen" 또는 "book-open")을 렌더링한다. */
export function Icon({ name, className }: { name: string; className?: string }) {
  const kebab = name
    .replace(/([a-z0-9])([A-Z])/g, "$1-$2")
    .replace(/([A-Z])([A-Z][a-z])/g, "$1-$2")
    .toLowerCase();
  const resolved = (known.has(kebab) ? kebab : "book-open") as IconName;
  return <DynamicIcon name={resolved} className={className} />;
}
