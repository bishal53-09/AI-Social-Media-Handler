"use client";

import { Film } from "lucide-react";
import { useState } from "react";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { MediaTable } from "@/components/media-table";
import { PageHeader } from "@/components/page-header";
import { ProjectSelect } from "@/components/project-select";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useApi } from "@/hooks/use-api";
import { useSelectedProject } from "@/hooks/use-selected-project";
import { api } from "@/lib/api";
import { formatBytes } from "@/lib/utils";

type StageFilter = "" | "raw" | "stitched";

export default function MediaPage() {
  const projects = useApi(() => api.projects.list(), []);
  const { selected, select } = useSelectedProject(projects.data?.items);
  const [stage, setStage] = useState<StageFilter>("");
  const media = useApi(
    () => api.projects.media(selected!, { limit: 500, stage: stage || undefined }),
    [selected, stage],
    { enabled: !!selected },
  );

  const total = media.data?.items.reduce((n, m) => n + m.size_bytes, 0) ?? 0;

  return (
    <>
      <PageHeader
        title="Media Library"
        description="Indexed footage and generated proxies for a project."
        actions={
          projects.data && projects.data.items.length > 0 ? (
            <>
              <label className="flex items-center gap-2 text-xs text-muted-foreground">
                Stage
                <select
                  className="h-8 rounded-md border border-input bg-card px-2 text-[13px] text-foreground"
                  value={stage}
                  onChange={(e) => setStage(e.target.value as StageFilter)}
                >
                  <option value="">All</option>
                  <option value="raw">Source videos</option>
                  <option value="stitched">360 stitched</option>
                </select>
              </label>
              <ProjectSelect projects={projects.data.items} value={selected} onChange={select} />
            </>
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
      ) : media.error ? (
        <ErrorState error={media.error} onRetry={media.reload} />
      ) : !media.data ? (
        <Skeleton className="h-32" />
      ) : media.data.items.length === 0 ? (
        <EmptyState
          icon={Film}
          title="No media indexed"
          description="Add videos from any device to media/raw (360 exports go in media/stitched), then open the project and click “Scan media”."
        />
      ) : (
        <Card className="py-0">
          <CardContent className="px-0">
            <MediaTable
              items={media.data.items}
              onRename={async (item, name) => {
                await api.projects.renameMedia(item.project_id, item.id, name);
                media.reload();
              }}
            />
            <div className="border-t px-3 py-2 text-xs text-muted-foreground">
              {media.data.total} file{media.data.total === 1 ? "" : "s"} · {formatBytes(total)}
            </div>
          </CardContent>
        </Card>
      )}
    </>
  );
}
