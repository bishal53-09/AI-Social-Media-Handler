"use client";

import { useState } from "react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useApi } from "@/hooks/use-api";
import { api, ApiError } from "@/lib/api";
import type { AppSettings, ContentPostDetail } from "@/types/api";

/** Platform + optional variant choices. Variants mirror what the backend accepts. */
const TARGETS = [
  { key: "instagram:reels", platform: "instagram", variant: "reels", label: "Instagram Reels" },
  {
    key: "instagram:carousel",
    platform: "instagram",
    variant: "carousel",
    label: "Instagram carousel (up to 10)",
  },
  { key: "tiktok:video", platform: "tiktok", variant: "video", label: "TikTok" },
  { key: "youtube:video", platform: "youtube", variant: "video", label: "YouTube video" },
  { key: "youtube:shorts", platform: "youtube", variant: "shorts", label: "YouTube Shorts" },
] as const;

export function NewPostForm({
  projectId,
  settings,
  onCreated,
}: {
  projectId: string;
  settings: AppSettings | null;
  onCreated: (post: ContentPostDetail) => void;
}) {
  const [title, setTitle] = useState("");
  const [files, setFiles] = useState<string[]>([]);
  const media = useApi(
    () => api.projects.media(projectId, { postable: true, limit: 500 }),
    [projectId],
  );
  const [caption, setCaption] = useState("");
  const [tags, setTags] = useState("");
  const [chosen, setChosen] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const enabled = new Set(settings?.platforms.filter((p) => p.enabled).map((p) => p.name));
  const options = TARGETS.filter((t) => !settings || enabled.has(t.platform));

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const platforms = TARGETS.filter((t) => chosen.includes(t.key)).map((t) => ({
        platform: t.platform,
        variant: t.variant,
      }));
      const created = await api.contentPosts.create({
        project_id: projectId,
        title,
        media_files: files,
        caption: caption || undefined,
        hashtags: tags
          .split(/[\s,]+/)
          .map((t) => t.replace(/^#/, ""))
          .filter(Boolean),
        platforms,
      });
      onCreated(created);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="grid max-w-xl gap-3">
      <p className="text-xs text-muted-foreground">
        Creates a draft for each platform. Nothing is published, and publishing is not implemented
        yet.
      </p>
      <div className="grid gap-1.5">
        <Label htmlFor="post-title">Title</Label>
        <Input
          id="post-title"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          required
          maxLength={200}
        />
      </div>
      <fieldset className="grid gap-1.5">
        <legend className="text-xs font-medium">
          Media ({files.length} selected, in the order you pick them)
        </legend>
        {!media.data ? (
          <p className="text-xs text-muted-foreground">Loading media…</p>
        ) : media.data.items.length === 0 ? (
          <p className="text-xs text-muted-foreground">
            This project has no media yet. Open the project and use “Add media” first.
          </p>
        ) : (
          <ul className="grid max-h-72 gap-1 overflow-y-auto rounded-md border p-1">
            {media.data.items.map((m) => {
              const picked = files.indexOf(m.relative_path);
              return (
                <li key={m.id}>
                  <label className="flex cursor-pointer items-center gap-2 rounded px-1.5 py-1 text-xs hover:bg-muted">
                    <input
                      type="checkbox"
                      checked={picked >= 0}
                      onChange={(e) =>
                        setFiles(
                          e.target.checked
                            ? [...files, m.relative_path]
                            : files.filter((f) => f !== m.relative_path),
                        )
                      }
                    />
                    {m.thumbnail_path ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={api.projects.thumbnailUrl(projectId, m.id)}
                        alt=""
                        className="size-10 rounded object-cover"
                      />
                    ) : (
                      <span className="grid size-10 place-items-center rounded bg-muted text-[10px] uppercase text-muted-foreground">
                        {m.kind}
                      </span>
                    )}
                    <span className="min-w-0 flex-1">
                      <span className="block truncate font-medium">{m.name}</span>
                      <span className="block truncate text-[11px] text-muted-foreground">
                        {m.stage}
                        {m.probe?.duration ? ` · ${Math.round(m.probe.duration)}s` : ""}
                      </span>
                    </span>
                    {picked >= 0 ? <span className="tabular-nums">#{picked + 1}</span> : null}
                  </label>
                </li>
              );
            })}
          </ul>
        )}
      </fieldset>
      <div className="grid gap-1.5">
        <Label htmlFor="post-caption">Caption</Label>
        <Input
          id="post-caption"
          value={caption}
          onChange={(e) => setCaption(e.target.value)}
          maxLength={5000}
        />
      </div>
      <div className="grid gap-1.5">
        <Label htmlFor="post-tags">Hashtags (space or comma separated)</Label>
        <Input id="post-tags" value={tags} onChange={(e) => setTags(e.target.value)} />
      </div>
      <fieldset className="grid gap-1.5">
        <legend className="text-xs font-medium">Platforms</legend>
        <div className="flex flex-wrap gap-3">
          {options.map((t) => (
            <label key={t.key} className="flex items-center gap-1.5 text-xs">
              <input
                type="checkbox"
                checked={chosen.includes(t.key)}
                onChange={(e) =>
                  setChosen(
                    e.target.checked ? [...chosen, t.key] : chosen.filter((k) => k !== t.key),
                  )
                }
              />
              {t.label}
            </label>
          ))}
        </div>
      </fieldset>
      {error ? (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}
      <div>
        <Button
          type="submit"
          disabled={busy || chosen.length === 0 || !title.trim() || files.length === 0}
        >
          {busy ? "Creating…" : "Create post"}
        </Button>
      </div>
    </form>
  );
}
