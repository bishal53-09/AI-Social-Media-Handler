"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FolderKanban, Plus } from "lucide-react";
import { useState } from "react";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { PageHeader } from "@/components/page-header";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Textarea } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { useApi } from "@/hooks/use-api";
import { api, ApiError } from "@/lib/api";
import { formatDateTime } from "@/lib/utils";

function CreateProjectForm({ mediaRoot, onCancel }: { mediaRoot?: string; onCancel: () => void }) {
  const router = useRouter();
  const [name, setName] = useState("");
  const [path, setPath] = useState("");
  const [description, setDescription] = useState("");
  const [camera, setCamera] = useState("");
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
        default_camera: camera.trim() || undefined,
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
          Creates the folder structure and <code className="font-mono">project.json</code>. Existing
          files are never overwritten.
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
          <div className="grid gap-1.5">
            <Label htmlFor="camera">Default camera</Label>
            <Input
              id="camera"
              value={camera}
              onChange={(e) => setCamera(e.target.value)}
              placeholder="Optional, e.g. iPhone 16"
            />
          </div>
          <div className="grid gap-1.5 sm:col-span-2">
            <Label htmlFor="path">Location</Label>
            <Input
              id="path"
              value={path}
              onChange={(e) => setPath(e.target.value)}
              placeholder={mediaRoot ? `${mediaRoot}/<project-name> (default)` : "default location"}
            />
            <p className="text-[11px] text-muted-foreground">
              Must be inside your configured project roots. Keep projects outside the Git
              repository.
            </p>
          </div>
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

export default function ProjectsPage() {
  const projects = useApi(() => api.projects.list(), []);
  const settings = useApi(() => api.settings(), []);
  const [creating, setCreating] = useState(false);

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

      {projects.error ? (
        <ErrorState error={projects.error} onRetry={projects.reload} />
      ) : !projects.data ? (
        <Skeleton className="h-32" />
      ) : projects.data.items.length === 0 ? (
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
      ) : (
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
      )}
    </>
  );
}
