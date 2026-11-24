"use client";

import { Film, LayoutGrid, Rows3 } from "lucide-react";
import { Suspense } from "react";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import {
  DateRangeFilter,
  FilterBar,
  Pagination,
  SearchBox,
  SelectFilter,
  SortControl,
} from "@/components/list-controls";
import { MediaGrid } from "@/components/media-grid";
import { useMediaPreview } from "@/components/media-preview";
import { MediaTable } from "@/components/media-table";
import { PageHeader } from "@/components/page-header";
import { ProjectSelect } from "@/components/project-select";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useApi } from "@/hooks/use-api";
import { useListState } from "@/hooks/use-list-state";
import { useSelectedProject } from "@/hooks/use-selected-project";
import { api } from "@/lib/api";

const FILTERS = ["q", "kind", "stage", "media_type", "from", "to", "sort", "order"];

function MediaLibrary() {
  const list = useListState(24);
  const projects = useApi(() => api.projects.list(), []);
  const { selected, select } = useSelectedProject(projects.data?.items);
  const urlProject = list.get("project");
  const project = projects.data?.items.some((p) => p.id === urlProject) ? urlProject : selected;
  const view = list.get("view") === "table" ? "table" : "grid";
  const sort = list.get("sort");
  const order = list.get("order") || "desc";

  const media = useApi(
    () =>
      api.projects.media(project!, {
        q: list.get("q"),
        kind: list.get("kind") || undefined,
        stage: list.get("stage") || undefined,
        media_type: list.get("media_type") || undefined,
        day_from: list.get("from") || undefined,
        day_to: list.get("to") || undefined,
        sort: sort || undefined,
        order: sort ? (order as "asc" | "desc") : undefined,
        limit: list.pageSize,
        offset: list.offset,
      }),
    [project, list.key],
    { enabled: !!project },
  );
  const preview = useMediaPreview();
  const items = media.data?.items ?? [];
  const filtered = FILTERS.some((k) => list.get(k));

  return (
    <>
      <PageHeader
        title="Media Library"
        description="Look through everything in a project, play videos and decide what to post."
        actions={
          projects.data && projects.data.items.length > 0 ? (
            <ProjectSelect
              projects={projects.data.items}
              value={project}
              onChange={(id) => {
                select(id);
                list.set({ project: id, ...Object.fromEntries(FILTERS.map((k) => [k, null])) });
              }}
            />
          ) : null
        }
      />
      {projects.error ? (
        <ErrorState error={projects.error} onRetry={projects.reload} />
      ) : !projects.data ? (
        <Skeleton className="h-32" />
      ) : projects.data.items.length === 0 ? (
        <EmptyState
          icon={Film}
          title="No projects"
          description="Create a project first, then add footage."
        />
      ) : (
        <>
          <FilterBar active={filtered} onClear={() => list.clear(FILTERS)}>
            <SearchBox
              value={list.get("q")}
              onChange={(q) => list.set({ q })}
              placeholder="Search file name…"
            />
            <SelectFilter
              label="Type"
              value={list.get("kind")}
              onChange={(kind) => list.set({ kind })}
              options={[
                { value: "video", label: "Videos" },
                { value: "image", label: "Photos" },
              ]}
            />
            <SelectFilter
              label="Stage"
              value={list.get("stage")}
              onChange={(stage) => list.set({ stage })}
              options={[
                { value: "raw", label: "Source videos" },
                { value: "stitched", label: "360 stitched" },
                { value: "processed", label: "Processed" },
                { value: "ready", label: "Ready to post" },
                { value: "posted", label: "Posted" },
                { value: "proxy", label: "Proxies" },
                { value: "thumbnail", label: "Thumbnails" },
                { value: "other", label: "Other" },
              ]}
            />
            <SelectFilter
              label="Format"
              value={list.get("media_type")}
              onChange={(media_type) => list.set({ media_type })}
              options={[
                { value: "flat", label: "Standard" },
                { value: "360", label: "360° original" },
                { value: "360-stitched", label: "360° stitched" },
                { value: "unknown", label: "Not scanned yet" },
              ]}
            />
            <DateRangeFilter
              label="Day"
              from={list.get("from")}
              to={list.get("to")}
              onChange={({ from, to }) => list.set({ from, to })}
            />
            <SortControl
              sort={sort}
              order={order}
              defaultLabel="Newest day"
              options={[
                { value: "day", label: "Day" },
                { value: "name", label: "File name" },
                { value: "size", label: "Size" },
                { value: "added", label: "Date added" },
              ]}
              onChange={({ sort, order }) => list.set({ sort, order })}
            />
            <div className="ml-auto flex gap-1">
              <Button
                variant={view === "grid" ? "default" : "outline"}
                size="sm"
                aria-pressed={view === "grid"}
                onClick={() => list.set({ view: "", page: "" })}
              >
                <LayoutGrid /> Grid
              </Button>
              <Button
                variant={view === "table" ? "default" : "outline"}
                size="sm"
                aria-pressed={view === "table"}
                onClick={() => list.set({ view: "table", page: "" })}
              >
                <Rows3 /> Table
              </Button>
            </div>
          </FilterBar>
          {media.error ? (
            <ErrorState error={media.error} onRetry={media.reload} />
          ) : !media.data ? (
            <Skeleton className="h-48" />
          ) : media.data.total === 0 ? (
            filtered ? (
              <EmptyState
                icon={Film}
                title="No media matches these filters"
                description="Try a different search or clear the filters."
              >
                <Button size="sm" variant="outline" onClick={() => list.clear(FILTERS)}>
                  Clear filters
                </Button>
              </EmptyState>
            ) : (
              <EmptyState
                icon={Film}
                title="No media indexed"
                description="Add videos from any device with “Add media” on the project page (360 exports go in media/stitched), then click “Scan media”."
              />
            )
          ) : (
            <Card className="py-0">
              <CardContent className="px-0">
                {view === "grid" ? (
                  <MediaGrid items={items} onPreview={(i) => preview.open(items, i)} />
                ) : (
                  <MediaTable
                    items={items}
                    onPreview={(i) => preview.open(items, i)}
                    onRename={async (item, name) => {
                      await api.projects.renameMedia(item.project_id, item.id, name);
                      media.reload();
                    }}
                  />
                )}
                <Pagination total={media.data.total} list={list} shown={items.length} noun="file" />
              </CardContent>
            </Card>
          )}
        </>
      )}
      {preview.node}
    </>
  );
}

export default function MediaPage() {
  return (
    <Suspense fallback={<Skeleton className="h-32" />}>
      <MediaLibrary />
    </Suspense>
  );
}
