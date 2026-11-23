import { Check, Minus } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { MediaTypeBadge } from "@/components/status-badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatBytes, formatDuration } from "@/lib/utils";
import type { MediaAsset } from "@/types/api";

function Flag({ on, label }: { on: boolean; label: string }) {
  return on ? (
    <Check className="size-4 text-success" aria-label={`${label}: yes`} />
  ) : (
    <Minus className="size-4 text-muted-foreground/50" aria-label={`${label}: no`} />
  );
}

export function MediaTable({ items }: { items: MediaAsset[] }) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>File</TableHead>
          <TableHead>Type</TableHead>
          <TableHead>Resolution</TableHead>
          <TableHead className="text-right">FPS</TableHead>
          <TableHead className="text-right">Duration</TableHead>
          <TableHead>Codec</TableHead>
          <TableHead className="text-right">Size</TableHead>
          <TableHead className="text-center">Thumb</TableHead>
          <TableHead className="text-center">Proxy</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {items.map((m) => (
          <TableRow key={m.id}>
            <TableCell className="max-w-72">
              <div className="truncate font-mono text-xs" title={m.relative_path}>
                {m.relative_path}
              </div>
              {m.probe_error ? (
                <Badge variant="destructive" className="mt-0.5" title={m.probe_error}>
                  probe failed
                </Badge>
              ) : null}
              {m.probe?.warnings?.length ? (
                <div className="text-[11px] text-warning" title={m.probe.warnings.join(" ")}>
                  {m.probe.warnings[0]}
                </div>
              ) : null}
            </TableCell>
            <TableCell>
              <MediaTypeBadge type={m.media_type} />
            </TableCell>
            <TableCell className="tabular-nums">
              {m.probe?.width ? `${m.probe.width}×${m.probe.height}` : "–"}
            </TableCell>
            <TableCell className="text-right tabular-nums">{m.probe?.fps ?? "–"}</TableCell>
            <TableCell className="text-right tabular-nums">
              {formatDuration(m.probe?.duration)}
            </TableCell>
            <TableCell className="text-xs">{m.probe?.video_codec ?? "–"}</TableCell>
            <TableCell className="text-right tabular-nums">{formatBytes(m.size_bytes)}</TableCell>
            <TableCell>
              <div className="flex justify-center">
                <Flag on={!!m.thumbnail_path} label="thumbnail" />
              </div>
            </TableCell>
            <TableCell>
              <div className="flex justify-center">
                <Flag on={!!m.proxy_path} label="proxy" />
              </div>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
