"use client";

import { FileVideo, MessageSquare, Plus } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Suspense, useState } from "react";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { MetricGrid } from "@/components/metrics";
import { NewPostForm } from "@/components/new-post-form";
import {
  DateRangeFilter,
  FilterBar,
  Pagination,
  SearchBox,
  SelectFilter,
  SortControl,
} from "@/components/list-controls";
import { PageHeader } from "@/components/page-header";
import { PostStatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useApi } from "@/hooks/use-api";
import { useListState } from "@/hooks/use-list-state";
import { useSelectedProject } from "@/hooks/use-selected-project";
import { api } from "@/lib/api";
import { formatDateTime } from "@/lib/utils";

const FILTERS = ["q", "status", "platform", "from", "to", "sort", "order"];
const POST_STATUSES = [
  "draft",
  "approved",
  "queued",
  "uploading",
  "processing",
  "published",
  "failed",
  "unknown",
  "cancelled",
];

function PostsList() {
  const list = useListState(12);
  const router = useRouter();
  const projects = useApi(() => api.projects.list(), []);
  const settings = useApi(() => api.settings(), []);
  const { selected, select } = useSelectedProject(projects.data?.items);
  const [creating, setCreating] = useState(false);
  const sort = list.get("sort");
  const order = list.get("order") || "desc";
  // "project" in the URL narrows the list; empty means posts from every project.
  const projectFilter = list.get("project");
  const posts = useApi(
    () =>
      api.contentPosts.list({
        project_id: projectFilter || undefined,
        q: list.get("q"),
        status: list.get("status") || undefined,
        platform: list.get("platform") || undefined,
        created_from: list.get("from") || undefined,
        created_to: list.get("to") || undefined,
        sort: sort || undefined,
        order: sort ? (order as "asc" | "desc") : undefined,
        limit: list.pageSize,
        offset: list.offset,
      }),
    [list.key],
  );
  const filtered = FILTERS.some((k) => list.get(k)) || !!projectFilter;
  const newPostProject = projectFilter || selected;

  return (
    <>
      <PageHeader
        title="Posts"
        description="Every post, where it was shared, and how it is performing on each platform."
        actions={
          <>
            <Button size="sm" onClick={() => setCreating(!creating)} disabled={!newPostProject}>
              <Plus /> New post
            </Button>
          </>
        }
      />

      {projects.error ? <ErrorState error={projects.error} onRetry={projects.reload} /> : null}

      {creating && newPostProject ? (
        <Card className="mb-4">
          <CardContent>
            <NewPostForm
              projectId={newPostProject}
              settings={settings.data}
              onCreated={(p) => router.push(`/posts/${p.id}`)}
            />
          </CardContent>
        </Card>
      ) : null}

      {projects.data && projects.data.items.length > 0 ? (
        <FilterBar active={filtered} onClear={() => list.clear([...FILTERS, "project"])}>
          <SearchBox
            value={list.get("q")}
            onChange={(q) => list.set({ q })}
            placeholder="Search title or caption…"
          />
          {projects.data.items.length > 1 ? (
            <SelectFilter
              label="Project"
              value={projectFilter}
              allLabel="All projects"
              onChange={(project) => {
                if (project) select(project);
                list.set({ project });
              }}
              options={projects.data.items.map((p) => ({ value: p.id, label: p.name }))}
            />
          ) : null}
          <SelectFilter
            label="Status"
            value={list.get("status")}
            onChange={(status) => list.set({ status })}
            options={POST_STATUSES.map((s) => ({ value: s, label: s }))}
          />
          <SelectFilter
            label="Platform"
            value={list.get("platform")}
            onChange={(platform) => list.set({ platform })}
            options={[
              { value: "instagram", label: "Instagram" },
              { value: "tiktok", label: "TikTok" },
              { value: "youtube", label: "YouTube" },
            ]}
          />
          <DateRangeFilter
            label="Created"
            from={list.get("from")}
            to={list.get("to")}
            onChange={({ from, to }) => list.set({ from, to })}
          />
          <SortControl
            sort={sort}
            order={order}
            defaultLabel="Newest first"
            options={[
              { value: "created", label: "Created" },
              { value: "title", label: "Title" },
            ]}
            onChange={({ sort, order }) => list.set({ sort, order })}
          />
        </FilterBar>
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
        <Skeleton className="h-32" />
      ) : posts.data.total === 0 && filtered ? (
        <EmptyState
          icon={FileVideo}
          title="No posts match these filters"
          description="Try different words or clear the filters."
        >
          <Button size="sm" variant="outline" onClick={() => list.clear([...FILTERS, "project"])}>
            Clear filters
          </Button>
        </EmptyState>
      ) : posts.data.total === 0 ? (
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
      {posts.data && posts.data.total > 0 ? (
        <Card className="mt-3 py-0">
          <Pagination
            total={posts.data.total}
            list={list}
            shown={posts.data.items.length}
            noun="post"
          />
        </Card>
      ) : null}
    </>
  );
}

export default function PostsPage() {
  return (
    <Suspense fallback={<Skeleton className="h-32" />}>
      <PostsList />
    </Suspense>
  );
}
