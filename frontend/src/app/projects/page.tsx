import type { Metadata } from "next";
import { ProjectsView } from "@/components/projects/projects-view";

export const metadata: Metadata = { title: "내 프로젝트" };

export default function ProjectsPage() {
  return <ProjectsView />;
}
