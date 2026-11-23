import { Badge } from "@/components/ui/badge";

type Variant = React.ComponentProps<typeof Badge>["variant"];

const JOB: Record<string, Variant> = {
  queued: "secondary",
  running: "default",
  completed: "success",
  failed: "destructive",
  cancelled: "outline",
};

const POST: Record<string, Variant> = {
  draft: "secondary",
  approved: "default",
  queued: "default",
  uploading: "default",
  processing: "default",
  published: "success",
  failed: "destructive",
  unknown: "warning",
  cancelled: "outline",
};

export function JobStatusBadge({ status }: { status: string }) {
  return <Badge variant={JOB[status] ?? "outline"}>{status}</Badge>;
}

export function PostStatusBadge({ status }: { status: string }) {
  return <Badge variant={POST[status] ?? "outline"}>{status}</Badge>;
}

export function MediaTypeBadge({ type }: { type: string }) {
  const label = type === "360-stitched" ? "360° stitched" : type === "360" ? "360° original" : type;
  return <Badge variant={type.startsWith("360") ? "default" : "secondary"}>{label}</Badge>;
}
