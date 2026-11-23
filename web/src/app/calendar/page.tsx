"use client";

import { CalendarDays, ChevronLeft, ChevronRight } from "lucide-react";
import { useMemo, useState } from "react";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { PageHeader } from "@/components/page-header";
import { ProjectSelect } from "@/components/project-select";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useApi } from "@/hooks/use-api";
import { useSelectedProject } from "@/hooks/use-selected-project";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

const pad = (n: number) => String(n).padStart(2, "0");

export default function CalendarPage() {
  const projects = useApi(() => api.projects.list(), []);
  const { selected, select } = useSelectedProject(projects.data?.items);
  const days = useApi(() => api.projects.days(selected!), [selected], { enabled: !!selected });
  const [cursor, setCursor] = useState(() => {
    const now = new Date();
    return { year: now.getFullYear(), month: now.getMonth() };
  });
  const [activeDay, setActiveDay] = useState<string | null>(null);
  const day = useApi(() => api.projects.day(selected!, activeDay!), [selected, activeDay], {
    enabled: !!selected && !!activeDay,
  });

  const counts = useMemo(
    () => new Map(days.data?.items.map((d) => [d.date, d.clip_count])),
    [days.data],
  );
  const first = new Date(cursor.year, cursor.month, 1);
  const offset = (first.getDay() + 6) % 7; // Monday first
  const length = new Date(cursor.year, cursor.month + 1, 0).getDate();
  const cells = Array.from(
    { length: Math.ceil((offset + length) / 7) * 7 },
    (_, i) => i - offset + 1,
  );
  const title = first.toLocaleDateString(undefined, { month: "long", year: "numeric" });
  const shift = (delta: number) =>
    setCursor(({ year, month }) => {
      const d = new Date(year, month + delta, 1);
      return { year: d.getFullYear(), month: d.getMonth() };
    });

  return (
    <>
      <PageHeader
        title="Calendar"
        description="Capture days recorded in the project's data/days files. Publishing schedules will appear here once publishing exists."
        actions={
          projects.data && projects.data.items.length > 0 ? (
            <ProjectSelect projects={projects.data.items} value={selected} onChange={select} />
          ) : null
        }
      />
      {projects.error ? (
        <ErrorState error={projects.error} onRetry={projects.reload} />
      ) : !projects.data ? (
        <Skeleton className="h-64" />
      ) : projects.data.items.length === 0 ? (
        <EmptyState
          icon={CalendarDays}
          title="No projects"
          description="Create a project to see its capture days."
        />
      ) : (
        <div className="grid gap-4 lg:grid-cols-3">
          <Card className="lg:col-span-2">
            <CardHeader className="flex-row items-center justify-between">
              <CardTitle>{title}</CardTitle>
              <div className="flex gap-1">
                <Button
                  variant="outline"
                  size="icon"
                  aria-label="Previous month"
                  onClick={() => shift(-1)}
                >
                  <ChevronLeft />
                </Button>
                <Button
                  variant="outline"
                  size="icon"
                  aria-label="Next month"
                  onClick={() => shift(1)}
                >
                  <ChevronRight />
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {days.error ? <ErrorState error={days.error} onRetry={days.reload} /> : null}
              <div className="grid grid-cols-7 gap-1 text-center text-[11px] text-muted-foreground">
                {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((d) => (
                  <div key={d}>{d}</div>
                ))}
              </div>
              <div className="mt-1 grid grid-cols-7 gap-1">
                {cells.map((n, i) => {
                  if (n < 1 || n > length) return <div key={i} />;
                  const iso = `${cursor.year}-${pad(cursor.month + 1)}-${pad(n)}`;
                  const count = counts.get(iso);
                  return (
                    <button
                      key={i}
                      disabled={!count}
                      onClick={() => setActiveDay(iso)}
                      className={cn(
                        "flex h-14 flex-col items-center justify-start rounded-md border p-1 text-xs transition-colors",
                        count
                          ? "cursor-pointer bg-accent/60 hover:border-primary"
                          : "text-muted-foreground/60",
                        activeDay === iso && "border-primary ring-2 ring-primary/30",
                      )}
                      aria-label={count ? `${iso}: ${count} clips` : iso}
                    >
                      <span>{n}</span>
                      {count ? <Badge className="mt-auto">{count}</Badge> : null}
                    </button>
                  );
                })}
              </div>
              {days.data && days.data.items.length === 0 ? (
                <p className="mt-3 text-xs text-muted-foreground">
                  No capture days yet. Scan the project to create day files.
                </p>
              ) : null}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>{activeDay ?? "Select a day"}</CardTitle>
            </CardHeader>
            <CardContent>
              {!activeDay ? (
                <p className="text-xs text-muted-foreground">
                  Click a highlighted day to see its clips.
                </p>
              ) : day.error ? (
                <ErrorState error={day.error} onRetry={day.reload} />
              ) : !day.data ? (
                <Skeleton className="h-20" />
              ) : (
                <ul className="divide-y text-xs">
                  {day.data.clips.map((c) => (
                    <li key={c.id} className="py-1.5">
                      <div className="font-medium">{c.title}</div>
                      <div
                        className="truncate font-mono text-[11px] text-muted-foreground"
                        title={c.source.file}
                      >
                        {c.source.file}
                      </div>
                      <div className="mt-1 flex gap-1">
                        <Badge variant="secondary">{c.source.type}</Badge>
                        <Badge
                          variant={c.processing.status === "completed" ? "success" : "outline"}
                        >
                          {c.processing.status}
                        </Badge>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </>
  );
}
