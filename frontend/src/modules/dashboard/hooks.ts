import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { ApiError } from "../../services/apiClient";

/** Filters kept in the URL query string, so links and refreshes preserve them. */
export function useUrlFilters<K extends string>(keys: readonly K[]) {
  const [searchParams, setSearchParams] = useSearchParams();
  const values = Object.fromEntries(keys.map((key) => [key, searchParams.get(key) ?? ""])) as Record<K, string>;

  const update = useCallback(
    (changes: Partial<Record<K, string>>) => {
      setSearchParams(
        (current) => {
          const next = new URLSearchParams(current);
          for (const [key, value] of Object.entries(changes) as [K, string][]) {
            if (value) next.set(key, value);
            else next.delete(key);
          }
          return next;
        },
        { replace: true },
      );
    },
    [setSearchParams],
  );

  const clear = useCallback(() => {
    setSearchParams(
      (current) => {
        const next = new URLSearchParams(current);
        keys.forEach((key) => next.delete(key));
        return next;
      },
      { replace: true },
    );
  }, [setSearchParams, keys.join(",")]);

  const active = keys.some((key) => values[key]);
  return { values, update, clear, active };
}

/** Loads data for `params` (compared by value), with loading/error state and a retry function. */
export function useApiData<T>(load: (params: Record<string, string>, signal: AbortSignal) => Promise<T>, params: Record<string, string>) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const key = JSON.stringify(params);
  const loadRef = useRef(load);
  loadRef.current = load;

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    loadRef
      .current(JSON.parse(key), controller.signal)
      .then(setData)
      .catch((err: Error) => {
        if (err.name === "AbortError") return;
        setData(null);
        // Filter problems come back as field errors (e.g. "Warehouse not found"); show those, not a form message.
        const fieldMessages = err instanceof ApiError ? Object.values(err.fieldErrors) : [];
        setError(
          fieldMessages.length
            ? `Invalid filter: ${fieldMessages.join("; ")}`
            : err instanceof ApiError
              ? err.message
              : "Something went wrong while loading this section.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [key, attempt]);

  const retry = useCallback(() => setAttempt((n) => n + 1), []);
  return { data, loading, error, retry };
}
