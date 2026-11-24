"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useMemo } from "react";

export interface ListState {
  /** Current value of a URL parameter ("" when absent). */
  get: (key: string) => string;
  /** Change filters. Any change except `page` itself returns to page 1. Empty values are removed. */
  set: (changes: Record<string, string | null | undefined>) => void;
  /** Remove all the given filters (and the page). */
  clear: (keys: string[]) => void;
  page: number;
  pageSize: number;
  /** Offset to send to the API. */
  offset: number;
  /** A stable string of the whole query: use it as a data-fetching dependency. */
  key: string;
}

/**
 * List filters, sorting and paging kept in the URL (`?q=beach&stage=raw&page=2`), so a filtered
 * view can be bookmarked, shared, reloaded and navigated with the back button.
 */
export function useListState(pageSize = 24): ListState {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const key = params.toString();

  const get = useCallback((k: string) => params.get(k) ?? "", [params]);

  const set = useCallback(
    (changes: Record<string, string | null | undefined>) => {
      const next = new URLSearchParams(params.toString());
      for (const [k, v] of Object.entries(changes)) {
        if (v === null || v === undefined || v === "") next.delete(k);
        else next.set(k, v);
      }
      if (!("page" in changes)) next.delete("page");
      const s = next.toString();
      router.replace(s ? `${pathname}?${s}` : pathname, { scroll: false });
    },
    [params, pathname, router],
  );

  const clear = useCallback(
    (keys: string[]) => {
      const next = new URLSearchParams(params.toString());
      for (const k of [...keys, "page"]) next.delete(k);
      const s = next.toString();
      router.replace(s ? `${pathname}?${s}` : pathname, { scroll: false });
    },
    [params, pathname, router],
  );

  const page = Math.max(1, Number.parseInt(params.get("page") ?? "1", 10) || 1);
  return useMemo(
    () => ({ get, set, clear, page, pageSize, offset: (page - 1) * pageSize, key }),
    [get, set, clear, page, pageSize, key],
  );
}
