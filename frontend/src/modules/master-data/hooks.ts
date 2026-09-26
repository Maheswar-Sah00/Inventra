import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError } from "../../services/apiClient";
import type { ListParams, Page } from "./types";

type Loader<T> = (params: ListParams, signal: AbortSignal) => Promise<Page<T>>;

/** Loads a page of results and reloads whenever `params` change (compared by value). */
export function usePagedList<T>(load: Loader<T>, params: ListParams) {
  const [data, setData] = useState<Page<T> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [version, setVersion] = useState(0);
  const key = JSON.stringify(params);
  const loadRef = useRef(load);
  loadRef.current = load;

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    loadRef
      .current(JSON.parse(key) as ListParams, controller.signal)
      .then((page) => setData(page))
      .catch((err: Error) => {
        if (err.name === "AbortError") return;
        setError(err instanceof ApiError ? err.message : "Unable to load data.");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [key, version]);

  const reload = useCallback(() => setVersion((v) => v + 1), []);
  return { data, loading, error, reload };
}

/** Returns `value` after it has stopped changing for `delay` ms (for search boxes). */
export function useDebouncedValue<T>(value: T, delay = 300): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delay);
    return () => window.clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}
