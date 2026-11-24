"use client";

import { ListChecks } from "lucide-react";
import { Suspense } from "react";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { hasActiveJob, JobTable } from "@/components/job-table";
import {
  DateRangeFilter,
  FilterBar,
  Pagination,
  SearchBox,
  SelectFilter,
  SortControl,
} from "@/components/list-controls";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useApi } from "@/hooks/use-api";
import { useListState } from "@/hooks/use-list-state";
import { api } from "@/lib/api";

const FILTERS = ["q", "status", "type", "project", "from", "to", "sort", "order"];
const STATUSES = ["queued", "running", "completed", "failed", "cancelled"];

function JobsList() {
  const list = useListState(25);
  const sort = list.get("sort");
  const order = list.get("order") || "desc";
  const projects = useApi(() => api.projects.list(), []);
  const jobs = useApi(
    () =>
      api.jobs.list({
        q: list.get("q"),
        status: list.get("status") || undefined,
        type: list.get("type") || undefined,
        project_id: list.get("project") || undefined,
        created_from: list.get("from") || undefined,
        created_to: list.get("to") || undefined,
        sort: sort || undefined,
        order: sort ? (order as "asc" | "desc") : undefined,
        limit: list.pageSize,
        offset: list.offset,
      }),
    [list.key],
    { pollMs: (d) => (hasActiveJob(d?.items) ? 1500 : 10000) },
  );
  const filtered = FILTERS.some((k) => list.get(k));

  return (
    <>
      <PageHeader
        title="Jobs"
        description="Background work: media scans and processing pipelines."
      />
      <FilterBar active={filtered} onClear={() => list.clear(FILTERS)}>
        <SearchBox
          value={list.get("q")}
          onChange={(q) => list.set({ q })}
          placeholder="Search job type or id…"
        />
        <SelectFilter
          label="Status"
          value={list.get("status")}
          onChange={(status) => list.set({ status })}
          options={STATUSES.map((s) => ({ value: s, label: s }))}
        />
        <SelectFilter
          label="Kind"
          value={list.get("type")}
          onChange={(type) => list.set({ type })}
          options={[
            { value: "media.scan", label: "Media scan" },
            { value: "pipeline.process", label: "Processing" },
          ]}
        />
        {projects.data && projects.data.items.length > 1 ? (
          <SelectFilter
            label="Project"
            value={list.get("project")}
            onChange={(project) => list.set({ project })}
            allLabel="All projects"
            options={projects.data.items.map((p) => ({ value: p.id, label: p.name }))}
          />
        ) : null}
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
            { value: "status", label: "Status" },
            { value: "type", label: "Kind" },
            { value: "progress", label: "Progress" },
          ]}
          onChange={({ sort, order }) => list.set({ sort, order })}
        />
      </FilterBar>
      {jobs.error ? (
        <ErrorState error={jobs.error} onRetry={jobs.reload} />
      ) : !jobs.data ? (
        <Skeleton className="h-32" />
      ) : jobs.data.total === 0 ? (
        filtered ? (
          <EmptyState icon={ListChecks} title="No jobs match these filters">
            <Button size="sm" variant="outline" onClick={() => list.clear(FILTERS)}>
              Clear filters
            </Button>
          </EmptyState>
        ) : (
          <EmptyState
            icon={ListChecks}
            title="No jobs"
            description="Jobs are created when you scan or process a project."
          />
        )
      ) : (
        <Card className="py-0">
          <CardContent className="px-0">
            <JobTable jobs={jobs.data.items} />
            <Pagination
              total={jobs.data.total}
              list={list}
              shown={jobs.data.items.length}
              noun="job"
            />
          </CardContent>
        </Card>
      )}
    </>
  );
}

export default function JobsPage() {
  return (
    <Suspense fallback={<Skeleton className="h-32" />}>
      <JobsList />
    </Suspense>
  );
}
