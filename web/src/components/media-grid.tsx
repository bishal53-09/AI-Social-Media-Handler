import { MediaThumb } from "@/components/media-preview";
import { MediaTypeBadge } from "@/components/status-badge";
import { formatBytes, formatDuration } from "@/lib/utils";
import type { MediaAsset } from "@/types/api";

/** Visual browsing of media: big thumbnails that open the preview. */
export function MediaGrid({
  items,
  onPreview,
}: {
  items: MediaAsset[];
  onPreview: (index: number) => void;
}) {
  return (
    <ul className="grid grid-cols-2 gap-3 p-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
      {items.map((m, i) => (
        <li key={m.id} className="grid min-w-0 gap-1.5">
          <MediaThumb asset={m} onOpen={() => onPreview(i)} className="aspect-video w-full" />
          <div className="min-w-0">
            <div className="truncate text-[13px] font-medium" title={m.name}>
              {m.name}
            </div>
            <div className="flex flex-wrap items-center gap-1.5 text-[11px] text-muted-foreground">
              <MediaTypeBadge type={m.media_type} />
              <span>{m.stage}</span>
              {m.probe?.duration ? <span>{formatDuration(m.probe.duration)}</span> : null}
              <span>{formatBytes(m.size_bytes)}</span>
            </div>
          </div>
        </li>
      ))}
    </ul>
  );
}
