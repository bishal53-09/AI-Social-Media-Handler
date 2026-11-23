"use client";

import { BarChart3 } from "lucide-react";
import Link from "next/link";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { MetricGrid, formatMetric } from "@/components/metrics";
import { PageHeader } from "@/components/page-header";
import { Alert, AlertDescription } from "@/components/ui/alert";
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
import { api } from "@/lib/api";
import { formatDateTime } from "@/lib/utils";

const COLUMNS = ["views", "likes", "comments", "shares", "saves"] as const;

export default function AnalyticsPage() {
  const overview = useApi(() => api.analytics.overview(), []);
  const o = overview.data;
  return (
    <>
      <PageHeader
        title="Analytics"
        description="Performance across all published posts, from the most recent sync of each platform."
      />
      {overview.error ? (
        <ErrorState error={overview.error} onRetry={overview.reload} />
      ) : !o ? (
        <Skeleton className="h-40" />
      ) : o.published_posts === 0 ? (
        <EmptyState
          icon={BarChart3}
          badge="Nothing published yet"
          title="No analytics to show"
          description="Analytics are collected from each platform's official API for published posts. Publishing and analytics collection are not implemented yet, so nothing is estimated or simulated here."
        >
          <Link href="/posts" className="text-xs underline">
            Go to Posts
          </Link>
        </EmptyState>
      ) : (
        <div className="grid gap-4">
          {o.posts_with_data < o.published_posts ? (
            <Alert variant="warning">
              <AlertDescription>
                {o.published_posts - o.posts_with_data} of {o.published_posts} published platform
                post
                {o.published_posts === 1 ? "" : "s"} have no analytics yet (never synced, or the
                platform integration cannot read them). Totals only cover posts with data.
              </AlertDescription>
            </Alert>
          ) : null}
          <Card>
            <CardHeader>
              <CardTitle>Totals</CardTitle>
              <CardDescription>
                {o.last_collected_at
                  ? `Latest snapshot ${formatDateTime(o.last_collected_at)}`
                  : "No snapshots yet."}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <MetricGrid metrics={o.totals} />
            </CardContent>
          </Card>
          <Card className="py-0">
            <CardHeader className="pt-4">
              <CardTitle>By platform</CardTitle>
            </CardHeader>
            <CardContent className="px-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Platform</TableHead>
                    <TableHead>Posts</TableHead>
                    {COLUMNS.map((c) => (
                      <TableHead key={c} className="text-right capitalize">
                        {c}
                      </TableHead>
                    ))}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {o.by_platform.map((b) => (
                    <TableRow key={b.platform}>
                      <TableCell>{b.platform_name}</TableCell>
                      <TableCell className="text-xs">
                        {b.posts_with_data}/{b.published_posts} with data
                      </TableCell>
                      {COLUMNS.map((c) => (
                        <TableCell key={c} className="text-right tabular-nums">
                          {b.totals[c] === undefined ? "–" : formatMetric(c, b.totals[c] ?? 0)}
                        </TableCell>
                      ))}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
          <Card className="py-0">
            <CardHeader className="pt-4">
              <CardTitle>Top posts by views</CardTitle>
            </CardHeader>
            <CardContent className="px-0">
              {o.top_posts.length === 0 ? (
                <p className="px-6 pb-4 text-xs text-muted-foreground">
                  No post has analytics yet.
                </p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Post</TableHead>
                      <TableHead>Platform</TableHead>
                      <TableHead className="text-right">Views</TableHead>
                      <TableHead className="text-right">Likes</TableHead>
                      <TableHead className="text-right">Comments</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {o.top_posts.map((t) => (
                      <TableRow key={t.platform_post_id}>
                        <TableCell>
                          {t.content_post_id ? (
                            <Link
                              href={`/posts/${t.content_post_id}`}
                              className="underline-offset-2 hover:underline"
                            >
                              {t.title}
                            </Link>
                          ) : (
                            t.title
                          )}
                        </TableCell>
                        <TableCell className="text-xs capitalize">{t.platform}</TableCell>
                        {(["views", "likes", "comments"] as const).map((k) => (
                          <TableCell key={k} className="text-right tabular-nums">
                            {t.metrics[k] === undefined ? "–" : formatMetric(k, t.metrics[k] ?? 0)}
                          </TableCell>
                        ))}
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </>
  );
}
