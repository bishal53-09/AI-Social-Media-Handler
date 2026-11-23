import { BarChart3 } from "lucide-react";
import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";

export default function AnalyticsPage() {
  return (
    <>
      <PageHeader
        title="Analytics"
        description="Performance of published posts across platforms."
      />
      <EmptyState
        icon={BarChart3}
        badge="Not implemented yet"
        title="No analytics to show"
        description="Analytics are collected from the platforms' official APIs once publishing exists (Phase 6). Nothing is estimated or simulated here."
      />
    </>
  );
}
