import { Badge } from "@/components/ui/badge";
import type { CapabilityName, CapabilityState } from "@/types/api";

export const CAPABILITY_LABELS: Record<CapabilityName, string> = {
  publish: "Publish video",
  analytics: "Read analytics",
  list_comments: "List comments",
  reply_comment: "Reply to comments",
  like_comment: "Like comments",
  hide_comment: "Hide / moderate comments",
  delete_comment: "Delete comments",
  like_post: "Like the post",
};

const VARIANT = { implemented: "success", planned: "warning", unavailable: "outline" } as const;
const TEXT: Record<CapabilityState, string> = {
  implemented: "available",
  planned: "planned, not built yet",
  unavailable: "not offered by the platform API",
};

export function CapabilityList({
  capabilities,
}: {
  capabilities: Partial<Record<CapabilityName, CapabilityState>>;
}) {
  return (
    <ul className="space-y-1.5 text-xs">
      {(Object.keys(CAPABILITY_LABELS) as CapabilityName[]).map((name) => {
        const state = capabilities[name] ?? "unavailable";
        return (
          <li key={name} className="flex items-center justify-between gap-3">
            <span>{CAPABILITY_LABELS[name]}</span>
            <Badge variant={VARIANT[state]}>{TEXT[state]}</Badge>
          </li>
        );
      })}
    </ul>
  );
}

/** Why a button is disabled, for its tooltip. */
export function whyDisabled(
  state: CapabilityState | undefined,
  platformName: string,
): string | null {
  if (state === "implemented") return null;
  if (state === "planned") return "Not implemented yet (see the roadmap).";
  return `Not offered by ${platformName}'s official API.`;
}
