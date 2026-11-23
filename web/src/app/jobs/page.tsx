"use client";

import { ListChecks } from "lucide-react";
import { useState } from "react";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { hasActiveJob, JobTable } from "@/components/job-table";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useApi } from "@/hooks/use-api";
import { api } from "@/lib/api";

const STATUSES = ["", "queued", "running", "completed", "failed", "cancelled"];

export default function JobsPage() {
  const [status, setStatus] = useState("");
  const jobs = useApi(() => api.jobs.list({ limit: 100, status: status || undefined }), [status], {
    pollMs: (d) => (hasActiveJob(d?.items) ? 1500 : 10000),
  });
  return (
    <>
      <PageHeader
        title="Jobs"
        description="Background work: media scans and processing pipelines."
        actions={
          <label className="flex items-center gap-2 text-xs text-muted-foreground">
            Status
            <select
              className="h-8 rounded-md border border-input bg-card px-2 text-[13px] text-foreground"
              value={status}
              onChange={(e) => setStatus(e.target.value)}
            >
              {STATUSES.map((s) => (
                <option key={s} value={s}>
                  {s || "All"}
                </option>
              ))}
            </select>
          </label>
        }
      />
      {jobs.error ? (
        <ErrorState error={jobs.error} onRetry={jobs.reload} />
      ) : !jobs.data ? (
        <Skeleton className="h-32" />
      ) : jobs.data.items.length === 0 ? (
        <EmptyState
          icon={ListChecks}
          title="No jobs"
          description="Jobs are created when you scan or process a project."
        />
      ) : (
        <Card className="py-0">
          <CardContent className="px-0">
            <JobTable jobs={jobs.data.items} />
          </CardContent>
        </Card>
      )}
    </>
  );
}
