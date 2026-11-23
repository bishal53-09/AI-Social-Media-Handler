import { Check, Minus, Pencil } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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

function NameCell({
  item,
  onRename,
}: {
  item: MediaAsset;
  onRename?: (item: MediaAsset, name: string | null) => Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(item.name);
  const [err, setErr] = useState<string | null>(null);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    try {
      await onRename?.(item, value.trim() || null);
      setEditing(false);
      setErr(null);
    } catch (error) {
      setErr(error instanceof Error ? error.message : String(error));
    }
  }

  if (editing) {
    return (
      <form onSubmit={save} className="flex items-center gap-1">
        <Input
          aria-label="Name"
          value={value}
          maxLength={200}
          autoFocus
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => e.key === "Escape" && setEditing(false)}
        />
        <Button type="submit" size="sm">
          Save
        </Button>
        {err ? <span className="text-[11px] text-destructive">{err}</span> : null}
      </form>
    );
  }
  return (
    <div className="flex items-center gap-1">
      <span className="truncate text-[13px] font-medium" title={item.name}>
        {item.name}
      </span>
      {onRename ? (
        <Button
          variant="ghost"
          size="sm"
          aria-label={`Rename ${item.name}`}
          onClick={() => {
            setValue(item.name);
            setEditing(true);
          }}
        >
          <Pencil />
        </Button>
      ) : null}
    </div>
  );
}

export function MediaTable({
  items,
  onRename,
}: {
  items: MediaAsset[];
  /** When given, each row can be renamed. Only the label changes; the file is not touched. */
  onRename?: (item: MediaAsset, name: string | null) => Promise<void>;
}) {
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
              <NameCell key={m.name} item={m} onRename={onRename} />
              <div
                className="truncate font-mono text-[11px] text-muted-foreground"
                title={m.relative_path}
              >
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
