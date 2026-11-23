"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft, Ban } from "lucide-react";
import { useState } from "react";
import { ErrorState } from "@/components/error-state";
import { PageHeader } from "@/components/page-header";
import { JobStatusBadge } from "@/components/status-badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { useApi } from "@/hooks/use-api";
import { api, ApiError } from "@/lib/api";
import { formatDateTime } from "@/lib/utils";

export default function JobDetailPage() {
  const { id } = useParams<{ id: string }>();
  const job = useApi(() => api.jobs.get(id), [id], {
    pollMs: (d) => (d && (d.status === "queued" || d.status === "running") ? 1000 : null),
  });
  const [cancelError, setCancelError] = useState<string | null>(null);

  async function cancel() {
    setCancelError(null);
    try {
      await api.jobs.cancel(id);
      job.reload();
    } catch (e) {
      setCancelError(e instanceof ApiError ? e.message : String(e));
    }
  }

  if (job.error) {
    return (
      <>
        <PageHeader title="Job" />
        <ErrorState error={job.error} onRetry={job.reload} />
      </>
    );
  }
  const j = job.data;
  const active = j && (j.status === "queued" || j.status === "running");

  return (
    <>
      <PageHeader
        title={j ? `Job ${j.id}` : "Job"}
        description={j?.type}
        actions={
          <>
            <Button asChild variant="ghost" size="sm">
              <Link href="/jobs">
                <ArrowLeft /> All jobs
              </Link>
            </Button>
            {active ? (
              <Button variant="outline" size="sm" onClick={cancel}>
                <Ban /> Cancel
              </Button>
            ) : null}
          </>
        }
      />
      {cancelError ? (
        <Alert variant="destructive" className="mb-3">
          <AlertDescription>{cancelError}</AlertDescription>
        </Alert>
      ) : null}
      {!j ? (
        <Skeleton className="h-40" />
      ) : (
        <div className="grid gap-4">
          <Card>
            <CardContent className="grid gap-3 sm:grid-cols-4">
              <div>
                <div className="text-[11px] text-muted-foreground">Status</div>
                <JobStatusBadge status={j.status} />
              </div>
              <div>
                <div className="text-[11px] text-muted-foreground">Started</div>
                {formatDateTime(j.started_at)}
              </div>
              <div>
                <div className="text-[11px] text-muted-foreground">Finished</div>
                {formatDateTime(j.finished_at)}
              </div>
              <div>
                <div className="text-[11px] text-muted-foreground">
                  Progress{j.current_stage && active ? ` · ${j.current_stage}` : ""}
                </div>
                <Progress value={j.progress * 100} className="mt-2" />
              </div>
              {j.error ? (
                <Alert variant="destructive" className="sm:col-span-4">
                  <AlertDescription>{j.error}</AlertDescription>
                </Alert>
              ) : null}
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Trace</CardTitle>
            </CardHeader>
            <CardContent>
              {j.events.length === 0 ? (
                <p className="text-xs text-muted-foreground">No events yet.</p>
              ) : (
                <ol className="space-y-1.5 text-xs">
                  {j.events.map((e) => (
                    <li key={e.id} className="flex gap-3">
                      <span className="w-36 shrink-0 text-muted-foreground tabular-nums">
                        {formatDateTime(e.created_at)}
                      </span>
                      <span className="w-20 shrink-0 font-medium">{e.event}</span>
                      <span className="w-24 shrink-0 text-muted-foreground">{e.stage ?? ""}</span>
                      <span className="min-w-0 break-words">{e.message}</span>
                    </li>
                  ))}
                </ol>
              )}
            </CardContent>
          </Card>
          {j.result ? (
            <Card>
              <CardHeader>
                <CardTitle>Result</CardTitle>
              </CardHeader>
              <CardContent>
                <pre className="max-h-80 overflow-auto rounded-md bg-muted p-2.5 font-mono text-[11px]">
                  {JSON.stringify(j.result, null, 2)}
                </pre>
              </CardContent>
            </Card>
          ) : null}
        </div>
      )}
    </>
  );
}
