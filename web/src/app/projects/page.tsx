"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FolderKanban, Plus } from "lucide-react";
import { Suspense, useState } from "react";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { FilterBar, Pagination, SearchBox, SortControl } from "@/components/list-controls";
import { PageHeader } from "@/components/page-header";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Textarea } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { useApi } from "@/hooks/use-api";
import { useListState } from "@/hooks/use-list-state";
import { api, ApiError } from "@/lib/api";
import { formatDateTime } from "@/lib/utils";

function CreateProjectForm({ mediaRoot, onCancel }: { mediaRoot?: string; onCancel: () => void }) {
  const router = useRouter();
  const [name, setName] = useState("");
  const [path, setPath] = useState("");
  const [description, setDescription] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const project = await api.projects.create({
        name: name.trim(),
        path: path.trim() || undefined,
        description: description.trim() || undefined,
      });
      router.push(`/projects/${project.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
      setBusy(false);
    }
  }

  return (
    <Card className="mb-4">
      <CardHeader>
        <CardTitle>New project</CardTitle>
        <CardDescription>
          Creates the project. Add your videos afterwards from the project page. Existing files are
          never overwritten.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={submit} className="grid gap-3 sm:grid-cols-2">
          <div className="grid gap-1.5">
            <Label htmlFor="name">Name *</Label>
            <Input
              id="name"
              required
              maxLength={200}
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="My Travel Project"
            />
          </div>
          <details className="sm:col-span-2">
            <summary className="cursor-pointer text-xs text-muted-foreground">
              Advanced: store this project somewhere else
            </summary>
            <div className="mt-2 grid gap-1.5">
              <Label htmlFor="path">Location</Label>
              <Input
                id="path"
                value={path}
                onChange={(e) => setPath(e.target.value)}
                placeholder={
                  mediaRoot ? `${mediaRoot}/<project-name> (default)` : "default location"
                }
              />
              <p className="text-[11px] text-muted-foreground">
                Must be inside your configured project roots. Keep projects outside the Git
                repository.
              </p>
            </div>
          </details>
          <div className="grid gap-1.5 sm:col-span-2">
            <Label htmlFor="description">Description</Label>
            <Textarea
              id="description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>
          {error ? (
            <Alert variant="destructive" className="sm:col-span-2">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          ) : null}
          <div className="flex gap-2 sm:col-span-2">
            <Button type="submit" disabled={busy || !name.trim()}>
              {busy ? "Creating…" : "Create project"}
            </Button>
            <Button type="button" variant="ghost" onClick={onCancel}>
              Cancel
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}

const FILTERS = ["q", "sort", "order"];

function ProjectsList() {
  const list = useListState(12);
  const sort = list.get("sort");
  const order = list.get("order") || "desc";
  const projects = useApi(
    () =>
      api.projects.list({
        q: list.get("q"),
        sort: sort || undefined,
        order: sort ? (order as "asc" | "desc") : undefined,
        limit: list.pageSize,
        offset: list.offset,
      }),
    [list.key],
  );
  const settings = useApi(() => api.settings(), []);
  const [creating, setCreating] = useState(false);
  const filtered = FILTERS.some((k) => list.get(k));

  return (
    <>
      <PageHeader
        title="Projects"
        description="Each project is an independent folder you can move between computers."
        actions={
          <Button size="sm" onClick={() => setCreating((c) => !c)}>
            <Plus /> New project
          </Button>
        }
      />
      {creating ? (
        <CreateProjectForm
          mediaRoot={settings.data?.media_root}
          onCancel={() => setCreating(false)}
        />
      ) : null}

      <FilterBar active={filtered} onClear={() => list.clear(FILTERS)}>
        <SearchBox
          value={list.get("q")}
          onChange={(q) => list.set({ q })}
          placeholder="Search name or description…"
        />
        <SortControl
          sort={sort}
          order={order}
          defaultLabel="Newest first"
          options={[
            { value: "name", label: "Name" },
            { value: "created", label: "Created" },
            { value: "updated", label: "Last updated" },
          ]}
          onChange={({ sort, order }) => list.set({ sort, order })}
        />
      </FilterBar>

      {projects.error ? (
        <ErrorState error={projects.error} onRetry={projects.reload} />
      ) : !projects.data ? (
        <Skeleton className="h-32" />
      ) : projects.data.total === 0 ? (
        filtered ? (
          <EmptyState
            icon={FolderKanban}
            title="No projects match your search"
            description="Try different words or clear the search."
          >
            <Button size="sm" variant="outline" onClick={() => list.clear(FILTERS)}>
              Clear filters
            </Button>
          </EmptyState>
        ) : (
          <EmptyState
            icon={FolderKanban}
            title="No projects yet"
            description="Create your first project to start organising footage."
          >
            {!creating ? (
              <Button size="sm" onClick={() => setCreating(true)}>
                <Plus /> New project
              </Button>
            ) : null}
          </EmptyState>
        )
      ) : (
        <>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {projects.data.items.map((p) => (
              <Link key={p.id} href={`/projects/${p.id}`} className="group">
                <Card className="h-full gap-2 transition-colors group-hover:border-primary/50">
                  <CardHeader>
                    <CardTitle className="text-[13px]">{p.name}</CardTitle>
                    <CardDescription className="truncate font-mono" title={p.path}>
                      {p.path}
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="text-xs text-muted-foreground">
                    {p.description ? <p className="mb-1 line-clamp-2">{p.description}</p> : null}
                    Created {formatDateTime(p.created_at)}
                  </CardContent>
                </Card>
              </Link>
            ))}
          </div>
          <Card className="mt-3 py-0">
            <Pagination
              total={projects.data.total}
              list={list}
              shown={projects.data.items.length}
              noun="project"
            />
          </Card>
        </>
      )}
    </>
  );
}

export default function ProjectsPage() {
  return (
    <Suspense fallback={<Skeleton className="h-32" />}>
      <ProjectsList />
    </Suspense>
  );
}
