"use client";

import Link from "next/link";
import {
  CheckCircle2,
  Circle,
  FolderKanban,
  Film,
  ListChecks,
  Plus,
  CalendarDays,
} from "lucide-react";
import { ErrorState } from "@/components/error-state";
import { hasActiveJob, JobTable } from "@/components/job-table";
import { PageHeader } from "@/components/page-header";
import { EmptyState } from "@/components/empty-state";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useApi } from "@/hooks/use-api";
import { api } from "@/lib/api";

function Stat({
  label,
  value,
  icon: Icon,
  hint,
}: {
  label: string;
  value: React.ReactNode;
  icon: typeof FolderKanban;
  hint?: string;
}) {
  return (
    <Card className="gap-1">
      <CardHeader className="flex-row items-center justify-between">
        <CardDescription>{label}</CardDescription>
        <Icon className="size-4 text-muted-foreground" />
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-semibold tabular-nums">{value}</div>
        {hint ? <div className="text-[11px] text-muted-foreground">{hint}</div> : null}
      </CardContent>
    </Card>
  );
}

function Step({ done, children }: { done: boolean; children: React.ReactNode }) {
  return (
    <li className="flex items-start gap-2">
      {done ? (
        <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-success" />
      ) : (
        <Circle className="mt-0.5 size-4 shrink-0 text-muted-foreground/50" />
      )}
      <span className={done ? "text-muted-foreground" : ""}>{children}</span>
    </li>
  );
}

export default function DashboardPage() {
  const overview = useApi(async () => {
    const [health, settings, projects] = await Promise.all([
      api.health(),
      api.settings(),
      api.projects.list(),
    ]);
    const details = await Promise.all(
      projects.items.slice(0, 25).map((p) => api.projects.get(p.id)),
    );
    return { health, settings, projects, details };
  }, []);
  const jobs = useApi(() => api.jobs.list({ limit: 8 }), [], {
    pollMs: (d) => (hasActiveJob(d?.items) ? 1500 : 10000),
  });

  if (overview.error) {
    return (
      <>
        <PageHeader title="Dashboard" />
        <ErrorState error={overview.error} onRetry={overview.reload} />
      </>
    );
  }

  const o = overview.data;
  const media = o?.details.reduce((n, d) => n + d.media_count, 0) ?? 0;
  const days = o?.details.reduce((n, d) => n + d.day_count, 0) ?? 0;
  const projectCount = o?.projects.total ?? 0;

  return (
    <>
      <PageHeader
        title="Dashboard"
        description="Overview of your projects, media and processing jobs."
        actions={
          <Button asChild size="sm">
            <Link href="/projects">
              <Plus /> New project
            </Link>
          </Button>
        }
      />

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {o ? (
          <>
            <Stat label="Projects" value={projectCount} icon={FolderKanban} />
            <Stat label="Media files" value={media} icon={Film} hint="indexed across projects" />
            <Stat label="Capture days" value={days} icon={CalendarDays} />
            <Stat
              label="Jobs"
              value={jobs.data?.total ?? "–"}
              icon={ListChecks}
              hint={hasActiveJob(jobs.data?.items) ? "work in progress" : "none running"}
            />
          </>
        ) : (
          Array.from({ length: 4 }, (_, i) => <Skeleton key={i} className="h-24" />)
        )}
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader className="flex-row items-center justify-between">
            <CardTitle>Recent jobs</CardTitle>
            <Button asChild variant="ghost" size="sm">
              <Link href="/jobs">View all</Link>
            </Button>
          </CardHeader>
          <CardContent className="px-0">
            {jobs.error ? (
              <div className="px-4">
                <ErrorState error={jobs.error} onRetry={jobs.reload} />
              </div>
            ) : jobs.data && jobs.data.items.length > 0 ? (
              <JobTable jobs={jobs.data.items} />
            ) : (
              <div className="px-4">
                <EmptyState
                  icon={ListChecks}
                  title="No jobs yet"
                  description="Jobs appear here when you scan media or generate thumbnails and proxies from a project."
                />
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Getting started</CardTitle>
            <CardDescription>Derived from your actual setup.</CardDescription>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2">
              <Step done={!!o}>API server is running</Step>
              <Step done={!!o?.settings.ffmpeg_available && !!o?.settings.ffprobe_available}>
                FFmpeg and ffprobe are installed
              </Step>
              <Step done={projectCount > 0}>
                <Link href="/projects" className="text-primary hover:underline">
                  Create a project
                </Link>
              </Step>
              <Step done={media > 0}>
                Add footage to <code className="font-mono text-xs">media/raw/&lt;date&gt;/</code>{" "}
                and scan
              </Step>
              <Step done={!!o?.settings.ai_key_configured}>
                Optional: set <code className="font-mono text-xs">ANTHROPIC_API_KEY</code> for AI
                features
              </Step>
            </ul>
          </CardContent>
        </Card>
      </div>
    </>
  );
}
