"use client";

import { ArrowDownAZ, ArrowUpAZ, ChevronLeft, ChevronRight, Search, X } from "lucide-react";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { ListState } from "@/hooks/use-list-state";
import { cn } from "@/lib/utils";

const selectClass =
  "h-8 rounded-md border border-input bg-card px-2 text-[13px] text-foreground shadow-xs outline-none focus-visible:ring-[3px] focus-visible:ring-ring";

export interface Option {
  value: string;
  label: string;
}

/** Search box that waits for a pause in typing before changing the URL (and so refetching). */
export function SearchBox({
  value,
  onChange,
  placeholder = "Search…",
  label = "Search",
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  label?: string;
}) {
  const [text, setText] = useState(value);
  // Follow the URL when it changes elsewhere (e.g. "Clear filters" or back button).
  const [seen, setSeen] = useState(value);
  if (value !== seen) {
    setSeen(value);
    setText(value);
  }
  useEffect(() => {
    if (text === value) return;
    const t = setTimeout(() => onChange(text.trim()), 300);
    return () => clearTimeout(t);
  }, [text, value, onChange]);

  return (
    <div className="relative min-w-48 flex-1 sm:max-w-72">
      <Search className="pointer-events-none absolute top-2 left-2 size-4 text-muted-foreground" />
      <Input
        type="search"
        aria-label={label}
        placeholder={placeholder}
        value={text}
        maxLength={100}
        className="pl-8"
        onChange={(e) => setText(e.target.value)}
      />
    </div>
  );
}

export function SelectFilter({
  label,
  value,
  options,
  onChange,
  allLabel = "All",
}: {
  label: string;
  value: string;
  options: Option[];
  onChange: (v: string) => void;
  /** Text of the "no filter" choice; pass null for selects that always have a value. */
  allLabel?: string | null;
}) {
  return (
    <label className="flex items-center gap-1.5 text-xs text-muted-foreground">
      {label}
      <select className={selectClass} value={value} onChange={(e) => onChange(e.target.value)}>
        {allLabel !== null ? <option value="">{allLabel}</option> : null}
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  );
}

export function DateRangeFilter({
  from,
  to,
  onChange,
  label = "Date",
}: {
  from: string;
  to: string;
  onChange: (changes: { from: string; to: string }) => void;
  label?: string;
}) {
  return (
    <fieldset className="flex items-center gap-1.5 text-xs text-muted-foreground">
      <legend className="sr-only">{label} range</legend>
      <span aria-hidden>{label}</span>
      <Input
        type="date"
        aria-label={`${label} from`}
        className="w-36"
        value={from}
        max={to || undefined}
        onChange={(e) => onChange({ from: e.target.value, to })}
      />
      <span aria-hidden>–</span>
      <Input
        type="date"
        aria-label={`${label} to`}
        className="w-36"
        value={to}
        min={from || undefined}
        onChange={(e) => onChange({ from, to: e.target.value })}
      />
    </fieldset>
  );
}

/** Sort field + direction toggle. `sort` empty means the endpoint's default order. */
export function SortControl({
  sort,
  order,
  options,
  defaultLabel,
  onChange,
}: {
  sort: string;
  order: string;
  options: Option[];
  defaultLabel: string;
  onChange: (changes: { sort: string; order: string }) => void;
}) {
  const desc = order !== "asc";
  return (
    <div className="flex items-center gap-1">
      <SelectFilter
        label="Sort"
        value={sort}
        options={options}
        allLabel={defaultLabel}
        onChange={(v) => onChange({ sort: v, order })}
      />
      <Button
        variant="outline"
        size="sm"
        disabled={!sort}
        aria-label={desc ? "Descending (click for ascending)" : "Ascending (click for descending)"}
        title={desc ? "Descending" : "Ascending"}
        onClick={() => onChange({ sort, order: desc ? "asc" : "desc" })}
      >
        {desc ? <ArrowDownAZ /> : <ArrowUpAZ />}
      </Button>
    </div>
  );
}

/** Row of filter controls with a "Clear filters" button shown while any filter is active. */
export function FilterBar({
  children,
  active,
  onClear,
  className,
}: {
  children: React.ReactNode;
  active: boolean;
  onClear: () => void;
  className?: string;
}) {
  return (
    <div className={cn("mb-3 flex flex-wrap items-center gap-x-4 gap-y-2", className)}>
      {children}
      {active ? (
        <Button variant="ghost" size="sm" onClick={onClear}>
          <X /> Clear filters
        </Button>
      ) : null}
    </div>
  );
}

/** "Showing 25–48 of 130" plus previous/next. Hidden when everything fits on one page. */
export function Pagination({
  total,
  list,
  shown,
  noun = "item",
}: {
  total: number;
  list: ListState;
  /** Number of items on the current page. */
  shown: number;
  noun?: string;
}) {
  const pages = Math.max(1, Math.ceil(total / list.pageSize));
  const first = shown === 0 ? 0 : list.offset + 1;
  const last = list.offset + shown;
  return (
    <nav
      aria-label="Pagination"
      className="flex flex-wrap items-center justify-between gap-2 border-t px-3 py-2 text-xs text-muted-foreground"
    >
      <span aria-live="polite">
        {total === 0
          ? `No ${noun}s`
          : `Showing ${first}–${last} of ${total} ${noun}${total === 1 ? "" : "s"}`}
      </span>
      {pages > 1 ? (
        <div className="flex items-center gap-1">
          <Button
            variant="outline"
            size="sm"
            disabled={list.page <= 1}
            onClick={() => list.set({ page: String(list.page - 1) })}
          >
            <ChevronLeft /> Previous
          </Button>
          <span className="px-1 tabular-nums">
            Page {list.page} of {pages}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={list.page >= pages}
            onClick={() => list.set({ page: String(list.page + 1) })}
          >
            Next <ChevronRight />
          </Button>
        </div>
      ) : null}
    </nav>
  );
}
