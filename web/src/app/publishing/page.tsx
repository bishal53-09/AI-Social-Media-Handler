"use client";

import { Send, ShieldCheck } from "lucide-react";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { PageHeader } from "@/components/page-header";
import { PostStatusBadge } from "@/components/status-badge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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

export default function PublishingPage() {
  const posts = useApi(() => api.posts.list(), []);
  const settings = useApi(() => api.settings(), []);
  const s = settings.data;

  return (
    <>
      <PageHeader
        title="Publishing"
        description="Review, approve and track posts. Nothing is published without approval."
      />
      <Alert className="mb-4">
        <div className="flex items-start gap-2">
          <ShieldCheck className="mt-0.5 size-4 shrink-0 text-success" />
          <div>
            <AlertTitle>
              Human approval is {s?.require_publish_approval === false ? "disabled" : "required"}
            </AlertTitle>
            <AlertDescription>
              Posts move draft → approved → queued → uploading → published. A lost upload response
              becomes “unknown” and must be reconciled with the platform before any retry, so a post
              is never duplicated.
            </AlertDescription>
          </div>
        </div>
      </Alert>

      {posts.error ? (
        <ErrorState error={posts.error} onRetry={posts.reload} />
      ) : posts.data && posts.data.items.length > 0 ? (
        <Card className="py-0">
          <CardContent className="px-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Platform</TableHead>
                  <TableHead>File</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Scheduled</TableHead>
                  <TableHead>Post ID</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {posts.data.items.map((p) => (
                  <TableRow key={p.id}>
                    <TableCell className="capitalize">
                      {p.platform}
                      {p.variant ? ` · ${p.variant}` : ""}
                    </TableCell>
                    <TableCell className="font-mono text-xs">{p.output_file}</TableCell>
                    <TableCell>
                      <PostStatusBadge status={p.status} />
                    </TableCell>
                    <TableCell className="text-xs">{formatDateTime(p.scheduled_at)}</TableCell>
                    <TableCell className="font-mono text-xs">{p.external_post_id ?? "–"}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      ) : posts.data ? (
        <EmptyState
          icon={Send}
          badge="Publishing not implemented"
          title="No posts"
          description="Platform publishing (Instagram, TikTok, YouTube) is planned for Phase 6. The post tracking, approval rules and state machine are in place and tested; the adapters cannot publish yet."
        />
      ) : null}

      {s ? (
        <Card className="mt-4">
          <CardHeader>
            <CardTitle>Platform adapters</CardTitle>
          </CardHeader>
          <CardContent className="px-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Platform</TableHead>
                  <TableHead>API</TableHead>
                  <TableHead>Credentials</TableHead>
                  <TableHead>Publishing</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {s.platforms.map((p) => (
                  <TableRow key={p.name}>
                    <TableCell className="capitalize">{p.name}</TableCell>
                    <TableCell className="text-xs text-muted-foreground">{p.api ?? "–"}</TableCell>
                    <TableCell>
                      <Badge variant={p.session_saved ? "success" : "outline"}>
                        {p.session_saved ? "login saved" : "not signed in"}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge variant={p.publishing_implemented ? "warning" : "outline"}>
                        {p.publishing_implemented ? "experimental" : "not implemented"}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      ) : null}
    </>
  );
}
