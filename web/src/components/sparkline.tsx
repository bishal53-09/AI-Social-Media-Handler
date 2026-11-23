import type { MetricSnapshot } from "@/types/api";

/** Tiny dependency-free line chart of one metric over the stored snapshots. */
export function Sparkline({ snapshots, metric }: { snapshots: MetricSnapshot[]; metric: string }) {
  const points = snapshots
    .map((s) => ({ t: new Date(s.collected_at).getTime(), v: s.metrics[metric] }))
    .filter((p): p is { t: number; v: number } => typeof p.v === "number");
  if (points.length < 2) {
    return (
      <p className="text-[11px] text-muted-foreground">Needs at least two syncs to show a trend.</p>
    );
  }
  const first = points[0];
  const last = points[points.length - 1];
  if (!first || !last) return null;
  const w = 240;
  const h = 48;
  const minT = first.t;
  const spanT = Math.max(last.t - minT, 1);
  const vs = points.map((p) => p.v);
  const minV = Math.min(...vs);
  const spanV = Math.max(Math.max(...vs) - minV, 1);
  const d = points
    .map((p, i) => {
      const x = ((p.t - minT) / spanT) * (w - 4) + 2;
      const y = h - 4 - ((p.v - minV) / spanV) * (h - 8);
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)} ${y.toFixed(1)}`;
    })
    .join(" ");
  return (
    <svg
      viewBox={`0 0 ${w} ${h}`}
      className="h-12 w-60 text-primary"
      role="img"
      aria-label={`${metric} over time, ${points.length} samples`}
    >
      <path d={d} fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" />
    </svg>
  );
}
