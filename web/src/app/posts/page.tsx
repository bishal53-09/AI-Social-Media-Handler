"use client";

import { FileVideo, MessageSquare, Plus } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { MetricGrid } from "@/components/metrics";
import { NewPostForm } from "@/components/new-post-form";
import { PageHeader } from "@/components/page-header";
import { ProjectSelect } from "@/components/project-select";
import { PostStatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useApi } from "@/hooks/use-api";
import { useSelectedProject } from "@/hooks/use-selected-project";
import { api } from "@/lib/api";
import { formatDateTime } from "@/lib/utils";

export default function PostsPage() {
  const router = useRouter();
  const projects = useApi(() => api.projects.list(), []);
  const settings = useApi(() => api.settings(), []);
  const { selected, select } = useSelectedProject(projects.data?.items);
  const [creating, setCreating] = useState(false);
  const posts = useApi(
    () => api.contentPosts.list({ project_id: selected ?? undefined }),
    [selected],
    {
      enabled: !!selected,
    },
  );

  return (
    <>
      <PageHeader
        title="Posts"
        description="Every post, where it was shared, and how it is performing on each platform."
        actions={
          <>
            {projects.data && selected ? (
              <ProjectSelect projects={projects.data.items} value={selected} onChange={select} />
            ) : null}
            <Button size="sm" onClick={() => setCreating(!creating)} disabled={!selected}>
              <Plus /> New post
            </Button>
          </>
        }
      />

      {projects.error ? <ErrorState error={projects.error} onRetry={projects.reload} /> : null}

      {creating && selected ? (
        <Card className="mb-4">
          <CardContent>
            <NewPostForm
              projectId={selected}
              settings={settings.data}
              onCreated={(p) => router.push(`/posts/${p.id}`)}
            />
          </CardContent>
        </Card>
      ) : null}

      {projects.data && projects.data.items.length === 0 ? (
        <EmptyState
          icon={FileVideo}
          title="Create a project first"
          description="Posts belong to a project. Create one on the Projects page."
        >
          <Button asChild size="sm">
            <Link href="/projects">Go to Projects</Link>
          </Button>
        </EmptyState>
      ) : posts.error ? (
        <ErrorState error={posts.error} onRetry={posts.reload} />
      ) : !posts.data ? (
        selected ? (
          <Skeleton className="h-32" />
        ) : null
      ) : posts.data.items.length === 0 ? (
        <EmptyState
          icon={FileVideo}
          title="No posts yet"
          description="A post is one video with a caption, shared to one or more platforms. Create one to track it here."
        />
      ) : (
        <ul className="grid gap-3">
          {posts.data.items.map((p) => (
            <li key={p.id}>
              <Link
                href={`/posts/${p.id}`}
                className="block rounded-xl focus-visible:ring-2 focus-visible:outline-none"
              >
                <Card className="gap-3 transition-colors hover:bg-accent/40">
                  <CardContent className="grid gap-3">
                    <div className="flex flex-wrap items-baseline justify-between gap-2">
                      <h2 className="text-sm font-semibold">{p.title}</h2>
                      <span className="text-[11px] text-muted-foreground">
                        {formatDateTime(p.created_at)}
                      </span>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {p.platform_posts.map((pp) => (
                        <span
                          key={pp.id}
                          className="inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-xs"
                        >
                          {pp.platform_name}
                          {pp.variant ? (
                            <span className="text-muted-foreground">· {pp.variant}</span>
                          ) : null}
                          <PostStatusBadge status={pp.status} />
                        </span>
                      ))}
                    </div>
                    {Object.keys(p.totals).length > 0 ? (
                      <MetricGrid
                        metrics={p.totals}
                        only={["views", "likes", "comments", "shares"]}
                      />
                    ) : (
                      <p className="text-[11px] text-muted-foreground">
                        No analytics collected yet.
                      </p>
                    )}
                    <p className="flex items-center gap-1 text-[11px] text-muted-foreground">
                      <MessageSquare className="size-3" /> {p.comment_total} comment
                      {p.comment_total === 1 ? "" : "s"} synced
                    </p>
                  </CardContent>
                </Card>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
