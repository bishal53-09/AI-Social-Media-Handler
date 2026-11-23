"use client";

import { ArrowLeft, ExternalLink, Heart, RefreshCw } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { CapabilityList, whyDisabled } from "@/components/capability-list";
import { CommentsPanel } from "@/components/comments-panel";
import { ErrorState } from "@/components/error-state";
import { MetricGrid } from "@/components/metrics";
import { PageHeader } from "@/components/page-header";
import { Sparkline } from "@/components/sparkline";
import { PostStatusBadge } from "@/components/status-badge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useApi } from "@/hooks/use-api";
import { api, ApiError } from "@/lib/api";
import { cn, formatDateTime } from "@/lib/utils";
import type { PlatformPostDetail, SyncReport } from "@/types/api";

function SyncResult({ report }: { report: SyncReport }) {
  const parts = [
    ["Comments", report.comments],
    ["Analytics", report.analytics],
  ] as const;
  return (
    <div className="grid gap-2">
      {parts.map(([label, part]) => (
        <Alert
          key={label}
          variant={
            part.status === "ok"
              ? "default"
              : part.status === "unsupported"
                ? "warning"
                : "destructive"
          }
        >
          <AlertTitle>
            {label}:{" "}
            {part.status === "ok"
              ? `synced (${part.count})`
              : part.status === "unsupported"
                ? "not available"
                : "failed"}
          </AlertTitle>
          {part.message ? <AlertDescription>{part.message}</AlertDescription> : null}
        </Alert>
      ))}
    </div>
  );
}

function PlatformPanel({ post, onChanged }: { post: PlatformPostDetail; onChanged: () => void }) {
  const [syncing, setSyncing] = useState(false);
  const [report, setReport] = useState<SyncReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [info, setInfo] = useState<string | null>(null);
  const published = post.status === "published";
  const likeOff = whyDisabled(post.capabilities.like_post, post.platform_name);

  async function sync() {
    setSyncing(true);
    setError(null);
    try {
      setReport(await api.engagement.sync(post.id));
      setRefreshKey((k) => k + 1);
      onChanged();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setSyncing(false);
    }
  }

  async function likePost() {
    setError(null);
    setInfo(null);
    try {
      await api.engagement.likePost(post.id, true);
      setInfo("Liked on the platform.");
      onChanged();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    }
  }

  return (
    <div className="grid gap-4">
      <Card>
        <CardHeader>
          <CardTitle className="flex flex-wrap items-center gap-2">
            {post.platform_name}
            {post.variant ? <Badge variant="outline">{post.variant}</Badge> : null}
            <PostStatusBadge status={post.status} />
          </CardTitle>
          <CardDescription>
            {published
              ? `Published ${formatDateTime(post.published_at)}`
              : post.scheduled_at
                ? `Scheduled for ${formatDateTime(post.scheduled_at)}`
                : "Not published. Publishing is not implemented yet, so this stays a draft."}
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3 text-xs">
          <div className="flex flex-wrap items-center gap-2">
            {post.external_url ? (
              <Button asChild size="sm" variant="outline">
                <a href={post.external_url} target="_blank" rel="noopener noreferrer">
                  <ExternalLink /> Open on {post.platform_name}
                </a>
              </Button>
            ) : null}
            <Button size="sm" onClick={sync} disabled={!published || syncing}>
              <RefreshCw className={cn(syncing && "animate-spin")} /> Sync from platform
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={likePost}
              disabled={!published || !!likeOff}
              title={likeOff ?? "Like this post as your account"}
            >
              <Heart /> Like post
            </Button>
          </div>
          {post.external_post_id ? (
            <p className="text-muted-foreground">
              Platform post ID: <code className="font-mono">{post.external_post_id}</code>
            </p>
          ) : null}
          {post.error ? (
            <Alert variant="destructive">
              <AlertDescription>{post.error}</AlertDescription>
            </Alert>
          ) : null}
          {error ? (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          ) : null}
          {info ? <p className="text-success">{info}</p> : null}
          {report ? <SyncResult report={report} /> : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Analytics</CardTitle>
          <CardDescription>
            {post.metrics_collected_at
              ? `Collected ${formatDateTime(post.metrics_collected_at)} · ${post.snapshots.length} snapshot${post.snapshots.length === 1 ? "" : "s"}`
              : "Nothing collected yet."}
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3">
          {Object.keys(post.metrics).length > 0 ? (
            <>
              <MetricGrid metrics={post.metrics} />
              <div>
                <div className="mb-1 text-[11px] text-muted-foreground">Views over time</div>
                <Sparkline snapshots={post.snapshots} metric="views" />
              </div>
            </>
          ) : (
            <p className="text-xs text-muted-foreground">
              {!published
                ? "Analytics exist only for published posts."
                : post.capabilities.analytics === "implemented"
                  ? "Press “Sync from platform” to collect the first snapshot."
                  : `Analytics for ${post.platform_name} are not implemented yet, so no numbers are shown.`}
            </p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Comments &amp; interactions</CardTitle>
          <CardDescription>Comments from {post.platform_name} and your replies.</CardDescription>
        </CardHeader>
        <CardContent>
          <CommentsPanel post={post} refreshKey={refreshKey} onChanged={onChanged} />
        </CardContent>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Capabilities</CardTitle>
            <CardDescription>What this platform integration can do.</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-2">
            <CapabilityList capabilities={post.capabilities} />
            {post.engagement_notes ? (
              <p className="text-[11px] text-muted-foreground">{post.engagement_notes}</p>
            ) : null}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Activity</CardTitle>
            <CardDescription>Interactions sent from this app, newest first.</CardDescription>
          </CardHeader>
          <CardContent className="px-0">
            {post.actions.length === 0 ? (
              <p className="px-6 text-xs text-muted-foreground">Nothing sent yet.</p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>When</TableHead>
                    <TableHead>Action</TableHead>
                    <TableHead>Result</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {post.actions.map((a) => (
                    <TableRow key={a.id}>
                      <TableCell className="text-xs">{formatDateTime(a.created_at)}</TableCell>
                      <TableCell className="text-xs">{a.action.replace(/_/g, " ")}</TableCell>
                      <TableCell>
                        <Badge variant={a.outcome === "succeeded" ? "success" : "destructive"}>
                          {a.outcome}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

export default function PostDetailPage() {
  const { id } = useParams<{ id: string }>();
  const post = useApi(() => api.contentPosts.get(id), [id]);
  const [active, setActive] = useState<string | null>(null);

  if (post.error) {
    return (
      <>
        <PageHeader title="Post" />
        <ErrorState error={post.error} onRetry={post.reload} />
      </>
    );
  }
  const p = post.data;
  if (!p) return <Skeleton className="h-64" />;
  const current = p.platform_posts.find((x) => x.id === active) ?? p.platform_posts[0];

  return (
    <>
      <PageHeader
        title={p.title}
        description={[p.output_file, p.caption].filter(Boolean).join(" · ")}
        actions={
          <Button asChild variant="ghost" size="sm">
            <Link href="/posts">
              <ArrowLeft /> All posts
            </Link>
          </Button>
        }
      />

      <Card className="mb-4">
        <CardHeader>
          <CardTitle>All platforms combined</CardTitle>
          <CardDescription>
            Totals add up platforms that have analytics (
            {p.platform_posts.filter((x) => Object.keys(x.metrics).length).length} of{" "}
            {p.platform_posts.length}). Reach and averages are not added.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {Object.keys(p.totals).length > 0 ? (
            <MetricGrid metrics={{ ...p.totals, comments_synced: p.comment_total }} />
          ) : (
            <p className="text-xs text-muted-foreground">No analytics collected yet.</p>
          )}
        </CardContent>
      </Card>

      <div className="mb-3">
        <h2 className="mb-1.5 text-xs font-medium text-muted-foreground">Shared to</h2>
        <div className="flex flex-wrap gap-2" role="tablist" aria-label="Platforms">
          {p.platform_posts.map((pp) => (
            <button
              key={pp.id}
              role="tab"
              aria-selected={pp.id === current?.id}
              onClick={() => setActive(pp.id)}
              className={cn(
                "inline-flex items-center gap-2 rounded-md border px-3 py-1.5 text-xs font-medium transition-colors hover:bg-accent",
                pp.id === current?.id && "border-primary bg-accent",
              )}
            >
              {pp.platform_name}
              {pp.variant ? <span className="text-muted-foreground">· {pp.variant}</span> : null}
              <PostStatusBadge status={pp.status} />
              <span className="text-muted-foreground">{pp.comment_count} 💬</span>
            </button>
          ))}
        </div>
      </div>

      {current ? <PlatformPanel key={current.id} post={current} onChanged={post.reload} /> : null}
    </>
  );
}
