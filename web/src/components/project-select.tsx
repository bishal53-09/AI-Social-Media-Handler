"use client";

import type { Project } from "@/types/api";

export function ProjectSelect({
  projects,
  value,
  onChange,
}: {
  projects: Project[];
  value: string | null;
  onChange: (id: string) => void;
}) {
  return (
    <label className="flex items-center gap-2 text-xs text-muted-foreground">
      Project
      <select
        className="h-8 rounded-md border border-input bg-card px-2 text-[13px] text-foreground shadow-xs outline-none focus-visible:ring-[3px] focus-visible:ring-ring"
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value)}
      >
        {projects.map((p) => (
          <option key={p.id} value={p.id}>
            {p.name}
          </option>
        ))}
      </select>
    </label>
  );
}
