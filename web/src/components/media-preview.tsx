"use client";

import { ChevronLeft, ChevronRight, Film, ImageIcon, Play, X } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { MediaTypeBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { cn, formatBytes, formatDuration } from "@/lib/utils";
import type { MediaAsset } from "@/types/api";

/** Video codecs every current browser can play. Anything else needs a proxy for preview. */
const BROWSER_CODECS = new Set(["h264", "vp8", "vp9", "av1"]);

export function canPlayInBrowser(a: MediaAsset): boolean {
  if (a.kind === "image") return !/\.(dng|heic)$/i.test(a.relative_path);
  if (a.proxy_path) return true;
  const codec = a.probe?.video_codec?.toLowerCase();
  return !codec || BROWSER_CODECS.has(codec); // unknown codec: try it, the player reports failures
}

/** Small picture of a media file. Clicking it (when `onOpen` is given) opens the preview. */
export function MediaThumb({
  asset,
  onOpen,
  className,
}: {
  asset: MediaAsset;
  onOpen?: () => void;
  className?: string;
}) {
  const [failed, setFailed] = useState(false);
  const src = asset.thumbnail_path
    ? api.projects.thumbnailUrl(asset.project_id, asset.id)
    : asset.kind === "image" && canPlayInBrowser(asset)
      ? api.projects.fileUrl(asset.project_id, asset.id, "original")
      : null;
  const body = (
    <>
      {src && !failed ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={src}
          alt=""
          loading="lazy"
          className="size-full object-cover"
          onError={() => setFailed(true)}
        />
      ) : asset.kind === "video" ? (
        <Film className="size-1/3 text-muted-foreground" />
      ) : (
        <ImageIcon className="size-1/3 text-muted-foreground" />
      )}
      {asset.kind === "video" && onOpen ? (
        <span className="absolute inset-0 grid place-items-center bg-black/0 opacity-80 transition group-hover:bg-black/25 group-hover:opacity-100">
          <span className="grid size-7 place-items-center rounded-full bg-black/60 text-white">
            <Play className="size-3.5 fill-current" />
          </span>
        </span>
      ) : null}
    </>
  );
  const box = cn(
    "group relative grid shrink-0 place-items-center overflow-hidden rounded-md bg-muted",
    className ?? "size-12",
  );
  return onOpen ? (
    <button
      type="button"
      onClick={onOpen}
      aria-label={`Preview ${asset.name}`}
      className={cn(
        box,
        "cursor-pointer outline-none focus-visible:ring-[3px] focus-visible:ring-ring",
      )}
    >
      {body}
    </button>
  ) : (
    <span className={box}>{body}</span>
  );
}

function Player({ asset }: { asset: MediaAsset }) {
  const [variant, setVariant] = useState<"auto" | "original">("auto");
  const [error, setError] = useState(false);
  const playable = canPlayInBrowser(asset);
  const src = api.projects.fileUrl(asset.project_id, asset.id, variant);
  const hasProxy = !!asset.proxy_path;

  if (!playable || error) {
    return (
      <div className="grid min-h-60 place-items-center gap-3 rounded-md bg-muted p-6 text-center">
        <MediaThumb asset={asset} className="h-40 w-64" />
        <p className="max-w-md text-xs text-muted-foreground">
          {asset.kind === "video"
            ? `This browser cannot play the original (${asset.probe?.video_codec ?? "unknown"} codec)${hasProxy ? "." : ", and no preview copy exists yet. Process the project to create a proxy, then preview it here."}`
            : "This image format cannot be shown in a browser."}{" "}
          The original file is not modified.
        </p>
        {error && hasProxy && variant === "auto" ? (
          <Button
            size="sm"
            variant="outline"
            onClick={() => {
              setVariant("original");
              setError(false);
            }}
          >
            Try the original
          </Button>
        ) : null}
      </div>
    );
  }
  return (
    <div className="grid gap-1.5">
      {asset.kind === "video" ? (
        <video
          key={src}
          src={src}
          controls
          autoPlay
          playsInline
          preload="metadata"
          poster={
            asset.thumbnail_path ? api.projects.thumbnailUrl(asset.project_id, asset.id) : undefined
          }
          className="max-h-[60vh] w-full rounded-md bg-black"
          onError={() => setError(true)}
        />
      ) : (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          key={src}
          src={api.projects.fileUrl(asset.project_id, asset.id, "original")}
          alt={asset.name}
          className="max-h-[60vh] w-full rounded-md bg-muted object-contain"
          onError={() => setError(true)}
        />
      )}
      {asset.kind === "video" && hasProxy ? (
        <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
          Playing {variant === "auto" ? "the lighter preview copy (proxy)" : "the original file"}.
          <button
            type="button"
            className="underline underline-offset-2"
            onClick={() => setVariant(variant === "auto" ? "original" : "auto")}
          >
            Play {variant === "auto" ? "original" : "preview copy"} instead
          </button>
        </div>
      ) : null}
    </div>
  );
}

/** Modal viewer for a media file, with previous/next through the list it was opened from. */
export function MediaPreviewDialog({
  items,
  index,
  onIndexChange,
  onClose,
  footer,
}: {
  items: MediaAsset[];
  index: number;
  onIndexChange: (i: number) => void;
  onClose: () => void;
  /** Optional extra content, e.g. a "Use in post" action. */
  footer?: (asset: MediaAsset) => React.ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const asset = items[index];

  useEffect(() => {
    const d = ref.current;
    if (d && !d.open) d.showModal();
  }, []);

  const go = useCallback(
    (delta: number) => {
      const n = index + delta;
      if (n >= 0 && n < items.length) onIndexChange(n);
    },
    [index, items.length, onIndexChange],
  );

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null;
      if (t && ["INPUT", "TEXTAREA", "SELECT", "VIDEO"].includes(t.tagName)) return;
      if (e.key === "ArrowLeft") go(-1);
      if (e.key === "ArrowRight") go(1);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [go]);

  if (!asset) return null;
  const probe = asset.probe;
  return (
    <dialog
      ref={ref}
      aria-label={`Preview: ${asset.name}`}
      onClose={onClose}
      onClick={(e) => e.target === ref.current && ref.current?.close()}
      className="m-auto w-[min(60rem,calc(100vw-2rem))] rounded-xl border bg-card p-0 text-card-foreground shadow-xl backdrop:bg-black/60"
    >
      <div className="grid gap-3 p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 className="truncate text-sm font-semibold" title={asset.name}>
              {asset.name}
            </h2>
            <p className="truncate font-mono text-[11px] text-muted-foreground">
              {asset.relative_path}
            </p>
          </div>
          <Button
            variant="ghost"
            size="icon"
            aria-label="Close preview"
            onClick={() => ref.current?.close()}
          >
            <X />
          </Button>
        </div>
        <Player key={asset.id} asset={asset} />
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
          <MediaTypeBadge type={asset.media_type} />
          <span>{asset.stage}</span>
          {probe?.width ? (
            <span className="tabular-nums">
              {probe.width}×{probe.height}
            </span>
          ) : null}
          {probe?.duration ? <span>{formatDuration(probe.duration)}</span> : null}
          {probe?.fps ? <span>{probe.fps} fps</span> : null}
          {probe?.video_codec ? <span>{probe.video_codec}</span> : null}
          <span>{formatBytes(asset.size_bytes)}</span>
          {asset.day ? <span>{asset.day}</span> : null}
        </div>
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-1">
            <Button variant="outline" size="sm" disabled={index <= 0} onClick={() => go(-1)}>
              <ChevronLeft /> Previous
            </Button>
            <span className="px-1 text-xs text-muted-foreground tabular-nums">
              {index + 1} / {items.length}
            </span>
            <Button
              variant="outline"
              size="sm"
              disabled={index >= items.length - 1}
              onClick={() => go(1)}
            >
              Next <ChevronRight />
            </Button>
          </div>
          {footer?.(asset)}
        </div>
      </div>
    </dialog>
  );
}

/** State for opening the preview from any list: `open(items, i)` and render `node` once. */
export function useMediaPreview(footer?: (asset: MediaAsset) => React.ReactNode) {
  const [state, setState] = useState<{ items: MediaAsset[]; index: number } | null>(null);
  const open = useCallback((items: MediaAsset[], index: number) => setState({ items, index }), []);
  const node = state ? (
    <MediaPreviewDialog
      items={state.items}
      index={state.index}
      onIndexChange={(index) => setState({ ...state, index })}
      onClose={() => setState(null)}
      footer={footer}
    />
  ) : null;
  return { open, node };
}
