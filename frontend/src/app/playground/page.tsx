import type { Metadata } from "next";
import { Playground } from "@/components/playground/playground";

export const metadata: Metadata = { title: "플레이그라운드" };

export default function PlaygroundPage() {
  return <Playground />;
}
