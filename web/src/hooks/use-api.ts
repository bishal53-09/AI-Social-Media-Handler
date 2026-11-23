"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "@/lib/api";

export interface ApiState<T> {
  data: T | null;
  error: ApiError | null;
  loading: boolean;
  reload: () => void;
}

/**
 * Minimal data-fetching hook: loads on mount (and when `deps` change), optionally polls.
 * `fetcher` must be stable per `deps` — wrap it in the caller's closure.
 */
export function useApi<T>(
  fetcher: () => Promise<T>,
  deps: readonly unknown[],
  options: { pollMs?: number | ((data: T | null) => number | null); enabled?: boolean } = {},
): ApiState<T> {
  const { pollMs, enabled = true } = options;
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(enabled);
  const isLoading = enabled && loading;
  const [tick, setTick] = useState(0);
  const fetcherRef = useRef(fetcher);
  const pollRef = useRef(pollMs);
  useEffect(() => {
    fetcherRef.current = fetcher;
    pollRef.current = pollMs;
  });

  const reload = useCallback(() => setTick((t) => t + 1), []);

  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    const run = async () => {
      try {
        const result = await fetcherRef.current();
        if (cancelled) return;
        setData(result);
        setError(null);
        const p = pollRef.current;
        const interval = typeof p === "function" ? p(result) : p;
        if (interval) timer = setTimeout(run, interval);
      } catch (e) {
        if (cancelled) return;
        setError(e instanceof ApiError ? e : new ApiError(String(e), 0));
        const p = pollRef.current;
        if (p) timer = setTimeout(run, 5000);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    run();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick, enabled]);

  return { data, error, loading: isLoading, reload };
}
