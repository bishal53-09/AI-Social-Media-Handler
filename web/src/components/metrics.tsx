import { cn } from "@/lib/utils";
import type { Metrics } from "@/types/api";

export const METRIC_LABELS: Record<string, string> = {
  views: "Views",
  likes: "Likes",
  comments: "Comments",
  comments_synced: "Comments synced",
  shares: "Shares",
  saves: "Saves",
  reach: "Reach",
  impressions: "Impressions",
  watch_time_seconds: "Watch time",
  avg_view_duration_seconds: "Avg. view",
};

export function formatMetric(key: string, value: number): string {
  if (key === "watch_time_seconds" || key === "avg_view_duration_seconds") {
    if (value >= 3600) return `${(value / 3600).toFixed(1)} h`;
    if (value >= 60) return `${(value / 60).toFixed(1)} min`;
    return `${Math.round(value)} s`;
  }
  return new Intl.NumberFormat(undefined, {
    notation: value >= 100000 ? "compact" : "standard",
  }).format(value);
}

const ORDER = Object.keys(METRIC_LABELS);

export function MetricGrid({
  metrics,
  className,
  only,
}: {
  metrics: Metrics;
  className?: string;
  only?: string[];
}) {
  const keys = (only ?? Object.keys(metrics)).filter((k) => metrics[k] !== undefined);
  keys.sort((a, b) => ((ORDER.indexOf(a) + 100) % 100) - ((ORDER.indexOf(b) + 100) % 100));
  return (
    <dl className={cn("grid grid-cols-2 gap-3 sm:grid-cols-4", className)}>
      {keys.map((k) => (
        <div key={k}>
          <dt className="text-[11px] text-muted-foreground">{METRIC_LABELS[k] ?? k}</dt>
          <dd className="text-lg font-semibold tabular-nums">{formatMetric(k, metrics[k] ?? 0)}</dd>
        </div>
      ))}
    </dl>
  );
}
