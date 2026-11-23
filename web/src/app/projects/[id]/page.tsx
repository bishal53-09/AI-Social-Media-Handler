"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { CalendarDays, Cog, Film, RefreshCw, Upload } from "lucide-react";
import { useRef, useState } from "react";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { hasActiveJob, JobTable } from "@/components/job-table";
import { MediaTable } from "@/components/media-table";
import { PageHeader } from "@/components/page-header";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useApi } from "@/hooks/use-api";
import { api, ApiError } from "@/lib/api";
import { formatDateTime } from "@/lib/utils";
import type { MediaAsset, ScanResult } from "@/types/api";

export default function ProjectDetailPage() {
  const { id } = useParams<{ id: string }>();
  const project = useApi(() => api.projects.get(id), [id]);
  const media = useApi(() => api.projects.media(id, { limit: 200 }), [id]);
  const days = useApi(() => api.projects.days(id), [id]);
  const jobs = useApi(() => api.jobs.list({ project_id: id, limit: 6 }), [id], {
    pollMs: (d) => (hasActiveJob(d?.items) ? 1500 : null),
  });

  const fileInput = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState<"scan" | "process" | "upload" | null>(null);
  const [scan, setScan] = useState<ScanResult | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  async function runScan() {
    setBusy("scan");
    setActionError(null);
    try {
      setScan(await api.projects.scan(id));
      project.reload();
      media.reload();
      days.reload();
    } catch (e) {
      setActionError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  async function upload(files: FileList | null) {
    if (!files?.length) return;
    setBusy("upload");
    setActionError(null);
    try {
      await api.projects.uploadMedia(id, Array.from(files));
      project.reload();
      media.reload();
      days.reload();
    } catch (e) {
      setActionError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(null);
      if (fileInput.current) fileInput.current.value = "";
    }
  }

  async function rename(item: MediaAsset, name: string | null) {
    await api.projects.renameMedia(id, item.id, name);
    media.reload();
  }

  async function runProcess() {
    setBusy("process");
    setActionError(null);
    try {
      await api.jobs.create({ type: "pipeline.process", project_id: id });
      jobs.reload();
    } catch (e) {
      setActionError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  if (project.error) {
    return (
      <>
        <PageHeader title="Project" />
        <ErrorState error={project.error} onRetry={project.reload} />
      </>
    );
  }
  const p = project.data;
  const processing = hasActiveJob(jobs.data?.items);

  return (
    <>
      <PageHeader
        title={p?.name ?? "Project"}
        description={p?.description ?? undefined}
        actions={
          <>
            <input
              ref={fileInput}
              type="file"
              multiple
              hidden
              accept="video/*,image/*,.mkv,.mts,.m2ts,.insv,.osv,.dng,.heic"
              onChange={(e) => upload(e.target.files)}
            />
            <Button
              size="sm"
              onClick={() => fileInput.current?.click()}
              disabled={!p || busy !== null}
            >
              <Upload /> {busy === "upload" ? "Adding…" : "Add media"}
            </Button>
            <Button variant="outline" size="sm" onClick={runScan} disabled={!p || busy !== null}>
              <RefreshCw className={busy === "scan" ? "animate-spin" : ""} />
              {busy === "scan" ? "Scanning…" : "Scan media"}
            </Button>
            <Button
              size="sm"
              onClick={runProcess}
              disabled={!p || busy !== null || processing || !media.data?.total}
            >
              <Cog /> {processing ? "Processing…" : "Generate thumbnails & proxies"}
            </Button>
          </>
        }
      />

      {actionError ? (
        <Alert variant="destructive" className="mb-3">
          <AlertDescription>{actionError}</AlertDescription>
        </Alert>
      ) : null}
      {p && !p.exists_on_disk ? (
        <Alert variant="warning" className="mb-3">
          <AlertTitle>Project folder not found</AlertTitle>
          <AlertDescription>
            <code className="font-mono">{p.path}</code> is missing or has no project.json. Restore
            the folder or re-register the project from its new location (
            <code className="font-mono">python -m app.cli scan &lt;path&gt;</code>).
          </AlertDescription>
        </Alert>
      ) : null}
      {scan ? (
        <Alert className="mb-3">
          <AlertTitle>Scan finished</AlertTitle>
          <AlertDescription>
            {scan.new} new, {scan.changed} changed, {scan.unchanged} unchanged, {scan.missing}{" "}
            missing · {scan.probed} probed{scan.probe_failed ? `, ${scan.probe_failed} failed` : ""}
            {scan.warnings.length ? (
              <ul className="mt-1 list-disc pl-4 text-warning">
                {scan.warnings.slice(0, 5).map((w) => (
                  <li key={w}>{w}</li>
                ))}
              </ul>
            ) : null}
          </AlertDescription>
        </Alert>
      ) : null}

      <div className="grid gap-3 sm:grid-cols-3">
        <Card className="sm:col-span-2">
          <CardHeader>
            <CardTitle>Details</CardTitle>
          </CardHeader>
          <CardContent>
            {p ? (
              <dl className="grid grid-cols-[7rem_1fr] gap-y-1.5 text-xs">
                <dt className="text-muted-foreground">Location</dt>
                <dd className="font-mono break-all">{p.path}</dd>
                <dt className="text-muted-foreground">Project ID</dt>
                <dd className="font-mono">{p.id}</dd>
                {p.settings?.default_camera ? (
                  <>
                    <dt className="text-muted-foreground">Default camera</dt>
                    <dd>{p.settings.default_camera}</dd>
                  </>
                ) : null}
                <dt className="text-muted-foreground">Created</dt>
                <dd>{formatDateTime(p.created_at)}</dd>
              </dl>
            ) : (
              <Skeleton className="h-20" />
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Contents</CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-2 gap-2">
            <div>
              <div className="text-2xl font-semibold tabular-nums">{p?.media_count ?? "–"}</div>
              <div className="text-[11px] text-muted-foreground">media files</div>
            </div>
            <div>
              <div className="text-2xl font-semibold tabular-nums">{p?.day_count ?? "–"}</div>
              <div className="text-[11px] text-muted-foreground">capture days</div>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card className="mt-4">
        <CardHeader className="flex-row items-center justify-between">
          <div>
            <CardTitle>Media inventory</CardTitle>
            <CardDescription>
              Use “Add media” to copy videos from any phone, camera or app into{" "}
              <code className="font-mono">media/raw/</code>. Originals are never modified or
              overwritten, and renaming only changes the name shown here.
            </CardDescription>
          </div>
          <Button asChild variant="ghost" size="sm">
            <Link href="/media">Media library</Link>
          </Button>
        </CardHeader>
        <CardContent className="px-0">
          {media.error ? (
            <div className="px-4">
              <ErrorState error={media.error} onRetry={media.reload} />
            </div>
          ) : !media.data ? (
            <Skeleton className="mx-4 h-24" />
          ) : media.data.items.length === 0 ? (
            <div className="px-4">
              <EmptyState
                icon={Film}
                title="No media indexed"
                description="Click “Add media” to choose videos or photos from your computer."
              />
            </div>
          ) : (
            <MediaTable items={media.data.items} onRename={rename} />
          )}
        </CardContent>
      </Card>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader className="flex-row items-center justify-between">
            <CardTitle>Capture days</CardTitle>
            <Button asChild variant="ghost" size="sm">
              <Link href="/calendar">Calendar</Link>
            </Button>
          </CardHeader>
          <CardContent>
            {days.data && days.data.items.length > 0 ? (
              <ul className="divide-y text-xs">
                {days.data.items
                  .slice()
                  .reverse()
                  .map((d) => (
                    <li key={d.date} className="flex items-center justify-between py-1.5">
                      <span className="flex items-center gap-2">
                        <CalendarDays className="size-3.5 text-muted-foreground" /> {d.date}
                      </span>
                      <Badge variant="secondary">
                        {d.clip_count} clip{d.clip_count === 1 ? "" : "s"}
                      </Badge>
                    </li>
                  ))}
              </ul>
            ) : (
              <p className="text-xs text-muted-foreground">
                Day files (<code className="font-mono">data/days/*.json</code>) are written when
                media is scanned.
              </p>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Recent jobs</CardTitle>
          </CardHeader>
          <CardContent className="px-0">
            {jobs.data && jobs.data.items.length > 0 ? (
              <JobTable jobs={jobs.data.items} />
            ) : (
              <p className="px-4 text-xs text-muted-foreground">No jobs for this project yet.</p>
            )}
          </CardContent>
        </Card>
      </div>
    </>
  );
}
