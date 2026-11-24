"use client";

import { useState } from "react";
import { MediaThumb, useMediaPreview } from "@/components/media-preview";
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

const PAGE = 48;

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
  const [search, setSearch] = useState("");
  const [kind, setKind] = useState("");
  const [shown, setShown] = useState(PAGE);
  const media = useApi(
    () =>
      api.projects.media(projectId, {
        postable: true,
        q: search || undefined,
        kind: kind || undefined,
        limit: shown,
      }),
    [projectId, search, kind, shown],
  );
  const toggle = (path: string, on: boolean) =>
    setFiles((cur) =>
      on ? (cur.includes(path) ? cur : [...cur, path]) : cur.filter((f) => f !== path),
    );
  const preview = useMediaPreview((a) => {
    const on = files.includes(a.relative_path);
    return (
      <Button
        type="button"
        size="sm"
        variant={on ? "outline" : "default"}
        onClick={() => toggle(a.relative_path, !on)}
      >
        {on ? "Remove from post" : "Use in post"}
      </Button>
    );
  });
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
        <div className="flex flex-wrap items-center gap-2">
          <Input
            type="search"
            aria-label="Search media"
            placeholder="Search media…"
            className="max-w-56"
            value={search}
            maxLength={100}
            onChange={(e) => {
              setSearch(e.target.value);
              setShown(PAGE);
            }}
          />
          <select
            aria-label="Media type"
            className="h-8 rounded-md border border-input bg-card px-2 text-[13px]"
            value={kind}
            onChange={(e) => {
              setKind(e.target.value);
              setShown(PAGE);
            }}
          >
            <option value="">Videos and photos</option>
            <option value="video">Videos</option>
            <option value="image">Photos</option>
          </select>
        </div>
        {!media.data ? (
          <p className="text-xs text-muted-foreground">Loading media…</p>
        ) : media.data.total === 0 ? (
          <p className="text-xs text-muted-foreground">
            {search || kind
              ? "No media matches. Clear the search to see everything."
              : "This project has no media yet. Open the project and use “Add media” first."}
          </p>
        ) : (
          <>
            <ul className="grid max-h-80 gap-1 overflow-y-auto rounded-md border p-1">
              {media.data.items.map((m, i) => {
                const picked = files.indexOf(m.relative_path);
                return (
                  <li
                    key={m.id}
                    className="flex items-center gap-2 rounded px-1.5 py-1 hover:bg-muted"
                  >
                    <MediaThumb
                      asset={m}
                      className="size-12"
                      onOpen={() => preview.open(media.data!.items, i)}
                    />
                    <label className="flex min-w-0 flex-1 cursor-pointer items-center gap-2 text-xs">
                      <input
                        type="checkbox"
                        checked={picked >= 0}
                        onChange={(e) => toggle(m.relative_path, e.target.checked)}
                      />
                      <span className="min-w-0 flex-1">
                        <span className="block truncate font-medium">{m.name}</span>
                        <span className="block truncate text-[11px] text-muted-foreground">
                          {m.stage}
                          {m.probe?.duration ? ` · ${Math.round(m.probe.duration)}s` : ""}
                          {m.day ? ` · ${m.day}` : ""}
                        </span>
                      </span>
                      {picked >= 0 ? <span className="tabular-nums">#{picked + 1}</span> : null}
                    </label>
                  </li>
                );
              })}
            </ul>
            <div className="flex items-center justify-between text-[11px] text-muted-foreground">
              <span>
                Showing {media.data.items.length} of {media.data.total}. Click a picture to preview.
              </span>
              {media.data.items.length < media.data.total ? (
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={() => setShown(shown + PAGE)}
                >
                  Show more
                </Button>
              ) : null}
            </div>
          </>
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
      {preview.node}
    </form>
  );
}
